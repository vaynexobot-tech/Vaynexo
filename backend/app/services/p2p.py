"""Avto P2P to'ldirish.

1. Foydalanuvchi summani tanlaydi (masalan 50 000). Tizim noyob summa beradi: 50 034.
2. Foydalanuvchi shu aniq summani kartaga o'tkazadi.
3. Kirim xabari keladi (SMS-forwarder → /api/p2p/incoming yoki admin bank xabarini botga forward qiladi).
4. Summasi mos keladigan YAGONA kutilayotgan to'ldirish topilsa — balans avtomatik to'ldiriladi.
   Topilmasa yoki bir nechta mos kelsa — admin qo'lda biriktiradi.
"""

import hashlib
import random
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError, BadState, NotFound
from app.models import IncomingPayment, Topup, User
from app.services import app_settings, wallet
from app.services.notify import Outbox, fmt, webapp_button

P2P_LOCK_ID = 7_201_001  # pg_advisory_xact_lock uchun


def now() -> datetime:
    return datetime.now(timezone.utc)


async def create_topup(session: AsyncSession, user_id: int, amount: int) -> Topup:
    from app.services import app_settings

    top = min(settings.topup_max, int(await app_settings.get_value(session, "topup_max_silver")))
    if amount < settings.topup_min or amount > top:
        raise AppError("bad_amount", f"Summa {fmt(settings.topup_min)} dan {fmt(top)} gacha bo'lishi kerak")
    # Bir vaqtda ikki foydalanuvchiga bir xil summa berilmasligi uchun.
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": P2P_LOCK_ID})
    # Foydalanuvchining eski kutilayotgan so'rovlari bekor qilinadi (kech to'lansa ham baribir topiladi).
    await session.execute(
        update(Topup).where(Topup.user_id == user_id, Topup.status == "pending").values(status="cancelled")
    )
    window_start = now() - timedelta(hours=settings.topup_late_match_hours)
    busy = set(
        await session.scalars(
            select(Topup.pay_amount).where(
                Topup.pay_amount.between(amount + 1, amount + 999),
                Topup.status.in_(("pending", "expired", "cancelled")),
                Topup.created_at >= window_start,
            )
        )
    )
    free = [s for s in range(1, 1000) if amount + s not in busy]
    if not free:
        raise AppError("busy", "Hozir bu summa band, boshqa summani tanlang yoki birozdan so'ng urining", 409)
    pay_amount = amount + random.choice(free)
    topup = Topup(
        user_id=user_id,
        requested_amount=amount,
        pay_amount=pay_amount,
        status="pending",
        expires_at=now() + timedelta(minutes=settings.topup_ttl_minutes),
    )
    session.add(topup)
    await session.flush()
    return topup


async def cancel_topup(session: AsyncSession, user_id: int, topup_id: int) -> None:
    topup = await session.scalar(select(Topup).where(Topup.id == topup_id, Topup.user_id == user_id).with_for_update().execution_options(populate_existing=True))
    if topup is None:
        raise NotFound("To'lov so'rovi")
    if topup.status == "pending":
        topup.status = "cancelled"


# ------------------------------------------------------------------ bank xabarini o'qish
_INCOME_WORDS = (
    "popolnen", "пополнен", "zachislen", "зачислен", "postuplen", "поступлен", "kirim", "tushdi",
    "perevod na kartu", "перевод на карту", "p2p", "o'tkazma", "otkazma", "received", "credit",
)
_EXPENSE_WORDS = ("spisan", "списан", "oplata", "оплата", "pokupka", "покупка", "chiqim", "yechildi", "snyat", "снят")
_AMOUNT_RE = re.compile(
    r"(?<![\d*•])([+]?\s?\d{1,3}(?:[ \u00a0.,]\d{3})+|\d+)(?:[.,](\d{1,2}))?\s*(?:uzs|сум|so['ʻ’]?m|sum)(?!\w)",
    re.IGNORECASE,
)


def parse_bank_message(raw: str) -> int | None:
    """Bank SMS / bildirishnomasidan kirim summasini oladi. Kirim bo'lmasa — None."""
    low = raw.lower()
    if any(w in low for w in _EXPENSE_WORDS) and not any(w in low for w in _INCOME_WORDS):
        return None
    if not any(w in low for w in _INCOME_WORDS) and "+" not in raw:
        return None
    m = _AMOUNT_RE.search(raw)
    if not m:
        return None
    whole = re.sub(r"[^\d]", "", m.group(1))
    if not whole:
        return None
    return int(whole)


def dedupe_key_for(source: str, raw: str | None, external_id: str | None, amount: int) -> str:
    base = external_id or f"{amount}|{(raw or '').strip()}"
    return f"{source}:" + hashlib.sha256(base.encode()).hexdigest()[:64]


async def _credit_topup(session: AsyncSession, topup: Topup, incoming: IncomingPayment | None, out: Outbox) -> None:
    topup.status = "paid"
    topup.paid_at = now()
    if incoming is not None:
        topup.incoming_id = incoming.id
        incoming.status = "matched"
        incoming.topup_id = topup.id
    await wallet.credit(
        session, topup.user_id, topup.pay_amount, "topup", f"topup:{topup.id}", ref_type="topup", ref_id=topup.id
    )
    out.user(topup.user_id, f"✅ Balans to'ldirildi: +{fmt(topup.pay_amount)}", webapp_button("Hamyonni ochish", "/wallet"))
    # Referal bonusi: do'sti birinchi marta to'ldirganda.
    user = await session.get(User, topup.user_id)
    bonus = await app_settings.get_value(session, "referral_bonus")
    min_topup = await app_settings.get_value(session, "referral_min_topup")
    # Bonus faqat /start uchun emas: do'st haqiqatan pul to'ldirgandan keyin va kamida min_topup summada.
    if bonus > 0 and user and user.referrer_id and not user.referral_paid and topup.pay_amount >= min_topup:
        user.referral_paid = True
        await wallet.credit(session, user.referrer_id, bonus, "referral", f"ref:{user.id}", ref_type="user", ref_id=user.id)
        out.user(user.referrer_id, f"🎁 Taklif qilgan do'stingiz hamyonini to'ldirdi. Bonus: +{fmt(bonus)}")


async def register_incoming(
    session: AsyncSession,
    amount: int,
    source: str,
    out: Outbox,
    raw_text: str | None = None,
    external_id: str | None = None,
) -> IncomingPayment | None:
    """Kirimni yozadi va mos to'ldirishni topadi. Takroriy xabar bo'lsa — None."""
    key = dedupe_key_for(source, raw_text, external_id, amount)
    if await session.scalar(select(IncomingPayment.id).where(IncomingPayment.dedupe_key == key)):
        return None
    incoming = IncomingPayment(amount=amount, source=source, raw_text=raw_text, dedupe_key=key)
    session.add(incoming)
    await session.flush()

    candidates = list(
        await session.scalars(
            select(Topup)
            .where(Topup.pay_amount == amount, Topup.status == "pending", Topup.expires_at > now())
            .with_for_update().execution_options(populate_existing=True)
        )
    )
    if not candidates:
        candidates = list(
            await session.scalars(
                select(Topup)
                .where(
                    Topup.pay_amount == amount,
                    Topup.status.in_(("pending", "expired", "cancelled")),
                    Topup.created_at >= now() - timedelta(hours=settings.topup_late_match_hours),
                )
                .with_for_update().execution_options(populate_existing=True)
            )
        )
    if len(candidates) == 1:
        await _credit_topup(session, candidates[0], incoming, out)
    else:
        reason = "mos so'rov topilmadi" if not candidates else f"{len(candidates)} ta so'rov mos keldi"
        out.admins(
            f"⚠️ Kirim avtomatik biriktirilmadi ({reason}).\nSumma: {fmt(amount)}\nManba: {source}\n"
            f"ID: {incoming.id}\nAdmin paneldan qo'lda biriktiring.",
            webapp_button("Admin panel", "/admin"),
        )
    return incoming


async def assign_incoming(session: AsyncSession, incoming_id: int, topup_id: int, out: Outbox) -> None:
    """Admin: biriktirilmagan kirimni so'rovga qo'lda biriktirish."""
    incoming = await session.scalar(select(IncomingPayment).where(IncomingPayment.id == incoming_id).with_for_update().execution_options(populate_existing=True))
    topup = await session.scalar(select(Topup).where(Topup.id == topup_id).with_for_update().execution_options(populate_existing=True))
    if incoming is None or topup is None:
        raise NotFound()
    if incoming.status != "unmatched" or topup.status == "paid":
        raise BadState("Kirim yoki so'rov allaqachon ishlatilgan")
    if incoming.amount != topup.pay_amount:
        topup.pay_amount = incoming.amount  # foydalanuvchi aslida qancha o'tkazgan bo'lsa, shuncha tushadi
    await _credit_topup(session, topup, incoming, out)


async def expire_topups(session: AsyncSession) -> int:
    res = await session.execute(
        update(Topup).where(Topup.status == "pending", Topup.expires_at <= now()).values(status="expired")
    )
    return res.rowcount or 0


async def unmatched_count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(IncomingPayment).where(IncomingPayment.status == "unmatched")) or 0
