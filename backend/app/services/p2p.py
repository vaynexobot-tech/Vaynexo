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

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError, BadState, NotFound
from app.models import IncomingPayment, P2PCard, Topup, User
from app.services import app_settings, wallet
from app.services.notify import Outbox, fmt, webapp_button

P2P_LOCK_ID = 7_201_001  # pg_advisory_xact_lock uchun
STEPS = 9  # hamma kartada band bo'lsa: +100 … +900 so'm


def last4(number: str | None) -> str:
    return re.sub(r"\D", "", number or "")[-4:]


_CARD_RE = re.compile(r"(?:\*{1,}|•+|x{2,}|X{2,}|\.{2,})\s?(\d{4})(?!\d)|\b\d{4,6}[*•xX]{2,}\d{0,4}?(\d{4})\b")


def parse_card_last4(raw: str | None) -> str | None:
    """Bank xabaridagi karta oxirgi 4 raqami: «*5276», «5614***5276», «••5276»."""
    if not raw:
        return None
    m = _CARD_RE.search(raw)
    if not m:
        return None
    return m.group(1) or m.group(2)


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
    checking = await session.scalar(select(func.count()).select_from(Topup).where(Topup.user_id == user_id, Topup.status == "checking"))
    if checking >= 2:
        raise BadState("Oldingi to'lovlaringiz tekshirilmoqda. Natijani kuting")
    cards = await active_cards(session)
    if not cards:
        raise AppError("no_card", "To'lov kartasi sozlanmagan. Birozdan so'ng urinib ko'ring", 503)
    window_start = now() - timedelta(hours=settings.topup_late_match_hours)
    # Band juftliklar: (karta, summa). Kech to'lov ham topilishi uchun yaqinda bekor bo'lganlar ham hisobga olinadi.
    busy = set((await session.execute(
        select(Topup.card_last4, Topup.pay_amount).where(
            Topup.pay_amount.between(amount, amount + 100 * STEPS),
            Topup.status.in_(("pending", "checking", "expired", "cancelled")),
            Topup.created_at >= window_start,
        )
    )).all())
    # Avval aynan so'ralgan summa — bo'sh kartaga; hamma kartada band bo'lsa +100, +200 ... (yaxlit summalar)
    random.shuffle(cards)
    pick = None
    for k in range(STEPS + 1):
        pay = amount + 100 * k
        card = next((c for c in cards if (last4(c["number"]), pay) not in busy), None)
        if card:
            pick = (card, pay)
            break
    if pick is None:
        raise AppError("busy", "Hozir bu summa band, birozdan so'ng urining yoki boshqa summa tanlang", 409)
    card, pay_amount = pick
    topup = Topup(
        user_id=user_id,
        requested_amount=amount,
        pay_amount=pay_amount,
        status="pending",
        expires_at=now() + timedelta(minutes=int(await app_settings.get_value(session, "topup_timeout_minutes"))),
        card_number=card["number"], card_holder=card["holder"], card_last4=last4(card["number"]),
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
    "perevod na kartu", "перевод на карту", "to'ldirildi", "toldirildi", "to'ldirish", "received", "credit", "➕",
)
_WEAK_INCOME = ("p2p", "o'tkazma", "otkazma", "perevod", "перевод")
_EXPENSE_WORDS = (
    "spisan", "списан", "oplata", "оплата", "pokupka", "покупка", "chiqim", "yechildi", "snyat", "снят",
    "perevod s kart", "перевод с карт", "platezh", "платеж", "платёж", "➖",
)
_AMOUNT_RE = re.compile(
    r"(?<![\d*•])([+]?\s?\d{1,3}(?:[ \u00a0.,]\d{3})+|\d+)(?:[.,](\d{1,2}))?\s*(?:uzs|сум|so['ʻ’]?m|sum)(?!\w)",
    re.IGNORECASE,
)


def parse_bank_message(raw: str) -> int | None:
    """Bank SMS / bildirishnomasidan kirim summasini oladi. Kirim bo'lmasa — None."""
    low = raw.lower()
    if "➖" in raw:  # bank botlari chiqimni ➖ bilan belgilaydi
        return None
    strong = "➕" in raw or any(w in low for w in _INCOME_WORDS)
    if any(w in low for w in _EXPENSE_WORDS) and not strong:
        return None
    if not strong and "+" not in raw and not any(w in low for w in _WEAK_INCOME):
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
    card4 = parse_card_last4(raw_text)
    if card4 and card4 not in {last4(c["number"]) for c in await active_cards(session)}:
        card4 = None  # xabardagi karta bizniki emas (yoki boshqa raqam) — faqat summa bo'yicha
    by_card = (or_(Topup.card_last4 == card4, Topup.card_last4.is_(None)),) if card4 else ()

    candidates = list(
        await session.scalars(
            select(Topup)
            .where(Topup.pay_amount == amount, *by_card,
                   or_(and_(Topup.status == "pending", Topup.expires_at > now()), Topup.status == "checking"))
            .with_for_update().execution_options(populate_existing=True)
        )
    )
    if not candidates:
        candidates = list(
            await session.scalars(
                select(Topup)
                .where(
                    Topup.pay_amount == amount, *by_card,
                    Topup.status.in_(("pending", "checking", "expired", "cancelled")),
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


# ------------------------------------------------------------------ kartalar
async def active_cards(session: AsyncSession) -> list[dict]:
    """Foydalanuvchiga ko'rsatiladigan kartalar. Admin panelda karta bo'lmasa — .env dagi karta."""
    rows = list(await session.scalars(select(P2PCard).where(P2PCard.active.is_(True)).order_by(P2PCard.sort, P2PCard.id)))
    if rows:
        return [{"id": c.id, "number": c.number, "holder": c.holder, "kind": c.kind} for c in rows]
    if settings.p2p_card_number:
        return [{"id": 0, "number": settings.p2p_card_number, "holder": settings.p2p_card_holder, "kind": ""}]
    return []


def card_kind(number: str) -> str:
    d = re.sub(r"\D", "", number)
    if d.startswith(("8600", "5614", "6262")):
        return "Uzcard"
    if d.startswith("9860"):
        return "Humo"
    if d.startswith("4"):
        return "Visa"
    if d[:2] in ("51", "52", "53", "54", "55"):
        return "Mastercard"
    return "Karta"


def clean_card(number: str) -> str:
    d = re.sub(r"\D", "", number or "")
    if len(d) != 16:
        raise AppError("bad_card", "Karta raqami 16 ta raqam bo'lsin")
    return " ".join(d[i:i + 4] for i in range(0, 16, 4))


# ------------------------------------------------------------------ «To'ladim» va admin tekshiruvi
def review_markup(topup_id: int) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Tasdiqlash", "callback_data": f"topup:ok:{topup_id}"},
        {"text": "❌ Rad etish", "callback_data": f"topup:no:{topup_id}"},
    ]]}


def review_text(t: Topup, user: User | None, minutes: int | None = None) -> str:
    who = (f"@{user.username}" if user and user.username else (user.first_name if user else "")) or "—"
    head = f"⏳ {minutes} daqiqada bank xabari kelmadi" if minutes else "💳 To'lov tekshiruvi"
    return (f"{head} — #{t.id}\n{who} · ID {t.user_id}\nSumma: {fmt(t.pay_amount)}\n"
            "Bank ilovasida aynan shu summa kartaga tushganini tekshiring.")


async def remind_unmatched(session: AsyncSession, out: Outbox) -> int:
    """«To'ladim» bosilgan, lekin bank xabari kelmagan to'lovlar haqida adminga bir marta xabar."""
    minutes = int(await app_settings.get_value(session, "topup_review_after_minutes"))
    rows = list(await session.scalars(
        select(Topup).where(Topup.status == "checking", Topup.review_sent.is_(False),
                            Topup.claimed_at <= now() - timedelta(minutes=minutes))
        .with_for_update(skip_locked=True).limit(50)
    ))
    for t in rows:
        t.review_sent = True
        user = await session.get(User, t.user_id)
        out.admins(review_text(t, user, minutes), review_markup(t.id))
    return len(rows)


async def claim_paid(session: AsyncSession, user_id: int, topup_id: int, has_receipt: bool = False) -> Topup:
    """Foydalanuvchi «To'ladim» bosdi: so'rov avtomatik tekshiruvga o'tadi.

    Bank xabari (SMS-forwarder yoki botga forward) kelishi bilan balans o'zi to'ldiriladi.
    Belgilangan vaqtda kelmasa — remind_unmatched() adminga tasdiqlash tugmalari bilan xabar yuboradi.
    """
    t = await session.scalar(select(Topup).where(Topup.id == topup_id, Topup.user_id == user_id)
                             .with_for_update().execution_options(populate_existing=True))
    if t is None:
        raise NotFound("To'lov so'rovi")
    if t.status == "paid":
        return t
    late_ok = t.status == "expired" and t.expires_at > now() - timedelta(minutes=30)
    if t.status != "pending" and not late_ok:
        raise BadState("Bu so'rov yopilgan. Yangi so'rov yarating")
    t.status, t.claimed_at, t.has_receipt = "checking", now(), has_receipt
    return t


async def admin_confirm(session: AsyncSession, topup_id: int, out: Outbox) -> Topup:
    t = await session.scalar(select(Topup).where(Topup.id == topup_id).with_for_update().execution_options(populate_existing=True))
    if t is None:
        raise NotFound("To'lov so'rovi")
    if t.status == "paid":
        raise BadState("Bu to'lov allaqachon tasdiqlangan")
    if t.status == "rejected":
        raise BadState("Bu to'lov rad etilgan")
    await _credit_topup(session, t, None, out)
    return t


async def admin_reject(session: AsyncSession, topup_id: int, reason: str | None, out: Outbox) -> Topup:
    t = await session.scalar(select(Topup).where(Topup.id == topup_id).with_for_update().execution_options(populate_existing=True))
    if t is None:
        raise NotFound("To'lov so'rovi")
    if t.status != "checking":
        raise BadState("Bu so'rov tekshiruvda emas")
    t.status = "rejected"
    t.reject_reason = (reason or "To'lov kartaga tushmagan").strip()[:300]
    out.user(t.user_id, f"❌ {fmt(t.pay_amount)} to'lovingiz tasdiqlanmadi.\nSabab: {t.reject_reason}\n"
             "Pul o'tkazgan bo'lsangiz, chekni @vaynexo_support ga yuboring.", webapp_button("Hamyon", "/wallet"))
    return t
