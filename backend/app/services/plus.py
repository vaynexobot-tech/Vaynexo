"""VAYNEXO Plus — oylik obuna.

Imtiyozlar: har bajarilgan xariddan keshbek (hamyonga), haftalik avto-xarid (masalan Weekly Pass har 7 kunda o'zi tushadi),
faqat Plus a'zolari uchun turnirlar, profil nishoni. To'lov hamyondan; avto-uzaytirish yoqilgan bo'lsa muddat tugashidan
oldin o'zi uzaytiriladi (pul yetmasa — ogohlantirish).
"""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError, BadState, InsufficientFunds, NotFound
from app.models import DonateGame, DonatePackage, PlusSub
from app.services import app_settings, wallet
from app.services.notify import Outbox, fmt, webapp_button

PERIOD = timedelta(days=30)
AUTO_EVERY = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_active(sub: PlusSub | None) -> bool:
    return bool(sub and sub.until > _now())


async def active(session: AsyncSession, user_id: int) -> bool:
    return is_active(await session.get(PlusSub, user_id))


async def enabled(session: AsyncSession) -> bool:
    return await app_settings.get_value(session, "plus_on") == "on"


async def _lock(session: AsyncSession, user_id: int) -> PlusSub | None:
    return await session.scalar(select(PlusSub).where(PlusSub.user_id == user_id).with_for_update().execution_options(populate_existing=True))


async def buy(session: AsyncSession, user_id: int) -> PlusSub:
    if not await enabled(session):
        raise BadState("VAYNEXO Plus hozircha yopiq")
    price = int(await app_settings.get_value(session, "plus_price"))
    sub = await _lock(session, user_id)
    if sub is None:
        sub = PlusSub(user_id=user_id, until=_now(), months=0, auto_renew=True, cashback_total=0, notice="")
        session.add(sub)
        await session.flush()
    n = (sub.months or 0) + 1
    await wallet.debit(session, user_id, price, "plus", f"plus:{user_id}:{n}", ref_type="plus", ref_id=user_id)
    sub.until = max(sub.until, _now()) + PERIOD
    sub.months = n
    sub.notice = ""
    return sub


async def set_options(session: AsyncSession, user_id: int, auto_renew: bool | None = None, package_id: int | None = None,
                      player_id: str | None = None, zone_id: str | None = None, clear_auto: bool = False) -> PlusSub:
    sub = await _lock(session, user_id)
    if sub is None:
        raise NotFound("Obuna")
    if auto_renew is not None:
        sub.auto_renew = auto_renew
    if clear_auto:
        sub.auto_package_id, sub.auto_next_at = None, None
    elif package_id is not None:
        pkg = await session.get(DonatePackage, package_id)
        if pkg is None or not pkg.is_active:
            raise NotFound("Paket")
        game = await session.get(DonateGame, pkg.game)
        fields = (game.fields if game else None) or []
        if pkg.delivery != "voucher" and (fields or pkg.game in ("ML", "MC")):
            if not re.fullmatch(r"[0-9A-Za-z_\-]{3,32}", (player_id or "").strip()):
                raise AppError("bad_id", "O'yin ID'sini to'g'ri kiriting")
        sub.auto_package_id = pkg.id
        sub.auto_player_id = (player_id or "").strip()[:64]
        sub.auto_zone_id = (zone_id or "").strip()[:64]
        sub.auto_next_at = _now()  # birinchi xarid darhol (keyingi cron'da)
    return sub


async def on_purchase(session: AsyncSession, user_id: int, kind: str, order_id: int, amount: int) -> int:
    """Bajarilgan xarid uchun keshbek (faqat faol Plus a'zolariga)."""
    sub = await session.get(PlusSub, user_id)
    if not is_active(sub) or amount <= 0:
        return 0
    pct = int(await app_settings.get_value(session, "plus_cashback"))
    cb = amount * pct // 100
    if cb <= 0:
        return 0
    entry = await wallet.credit(session, user_id, cb, "plus_cashback", f"plus_cb:{kind}:{order_id}", ref_type="plus", ref_id=user_id)
    if entry is not None:
        sub.cashback_total = (sub.cashback_total or 0) + cb
    return cb


async def overview(session: AsyncSession, user_id: int) -> dict:
    sub = await session.get(PlusSub, user_id)
    s = await app_settings.get_many(session, "plus_on", "plus_price", "plus_cashback")
    pkg = await session.get(DonatePackage, sub.auto_package_id) if sub and sub.auto_package_id else None
    return {
        "enabled": s["plus_on"] == "on", "price": int(s["plus_price"]), "cashback": int(s["plus_cashback"]),
        "active": is_active(sub),
        "until": sub.until.isoformat() if sub else None,
        "days_left": max(0, (sub.until - _now()).days) if is_active(sub) else 0,
        "months": sub.months if sub else 0,
        "auto_renew": sub.auto_renew if sub else True,
        "cashback_total": sub.cashback_total if sub else 0,
        "auto": {"package_id": pkg.id, "title": pkg.name, "price": pkg.price, "game": pkg.game, "player_id": sub.auto_player_id,
                 "zone_id": sub.auto_zone_id, "next_at": sub.auto_next_at.isoformat() if sub.auto_next_at else None} if pkg else None,
    }


async def tick(sessions: async_sessionmaker, out: Outbox) -> list[int]:
    """Avto-uzaytirish va haftalik avto-xarid. Yaratilgan donat buyurtmalari ID'larini qaytaradi (navbatga qo'yish uchun)."""
    from app.services import donate

    now = _now()
    orders: list[int] = []
    async with sessions() as session:
        renew_ids = list(await session.scalars(select(PlusSub.user_id).where(
            PlusSub.until <= now + timedelta(hours=12), PlusSub.until > now - timedelta(days=3))))
        auto_ids = list(await session.scalars(select(PlusSub.user_id).where(
            PlusSub.auto_package_id.is_not(None), PlusSub.auto_next_at <= now, PlusSub.until > now)))
    price = None
    for uid in renew_ids:
        async with sessions() as session:
            try:
                async with session.begin():
                    sub = await _lock(session, uid)
                    if sub is None or sub.until > now + timedelta(hours=12):
                        continue
                    if sub.auto_renew and await enabled(session):
                        try:
                            async with session.begin_nested():
                                await buy(session, uid)
                            out.user(uid, f"💎 VAYNEXO Plus yana 30 kunga uzaytirildi. Amal qiladi: {sub.until:%d.%m.%Y} gacha.")
                            continue
                        except InsufficientFunds:
                            await session.refresh(sub)
                            price = price or int(await app_settings.get_value(session, "plus_price"))
                            if not sub.notice:
                                sub.notice = "renew_fail"
                                out.user(uid, f"⚠️ VAYNEXO Plus'ni uzaytirish uchun hamyonda {fmt(price)} yetmayapti. "
                                              "Hamyonni to'ldiring — obuna avtomatik uzaytiriladi.", webapp_button("Hamyon", "/wallet"))
                    if sub.until <= now and sub.notice != "expired":
                        sub.notice = "expired"
                        out.user(uid, "⌛️ VAYNEXO Plus muddati tugadi. Keshbek va avto-xarid to'xtadi.", webapp_button("Uzaytirish", "/plus"))
            except Exception:
                continue
    for uid in auto_ids:
        async with sessions() as session:
            async with session.begin():
                sub = await _lock(session, uid)
                if sub is None or not sub.auto_package_id or not sub.auto_next_at or sub.auto_next_at > now or not is_active(sub):
                    continue
                try:
                    async with session.begin_nested():
                        order = await donate.create_order(session, uid, sub.auto_package_id, sub.auto_player_id, sub.auto_zone_id)
                    orders.append(order.id)
                    sub.auto_next_at = now + AUTO_EVERY
                    out.user(uid, f"🔁 Haftalik avto-xarid: {order.title} — {fmt(order.price)}. Yetkazilmoqda…", webapp_button("Tarix", "/history"))
                except InsufficientFunds:
                    await session.refresh(sub)
                    sub.auto_next_at = now + timedelta(days=1)
                    out.user(uid, "⚠️ Haftalik avto-xarid uchun hamyonda mablag' yetmadi. Ertaga yana urinamiz.", webapp_button("Hamyon", "/wallet"))
                except AppError as e:
                    await session.refresh(sub)
                    sub.auto_package_id, sub.auto_next_at = None, None
                    out.user(uid, f"⚠️ Avto-xarid to'xtatildi: {e.message}. Plus sahifasida qayta sozlang.", webapp_button("Plus", "/plus"))
    return orders
