"""Skin jamg'armasi: kutilayotgan skin/paket uchun pulni oz-ozdan yig'ish.

- Maqsad = tanlangan paket narxi. Pul hamyondan jamg'armaga o'tadi (bloklanadi), haftalik avto-yig'ish mumkin.
- Maqsadga yetgach «Sotib olish» (yoki belgilangan kuni avtomatik): yig'ilgan pul + bonus bilan buyurtma beriladi.
- Bonus faqat xaridga va faqat pulning yarmi kamida N kun jamg'armada turgan bo'lsa (bir kunda yig'ib bonus olishning oldi olinadi).
- Bekor qilinsa — yig'ilgan pul hamyonga to'liq qaytadi (bonus yo'q).
"""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError, BadState, InsufficientFunds, NotFound
from app.models import DonateOrder, DonatePackage, Saving
from app.services import app_settings, wallet
from app.services.notify import Outbox, fmt, webapp_button

MAX_ACTIVE = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _settings(session: AsyncSession) -> dict:
    s = await app_settings.get_many(session, "savings_on", "savings_bonus", "savings_min_days")
    return {"on": s["savings_on"] == "on", "bonus": int(s["savings_bonus"]), "min_days": int(s["savings_min_days"])}


async def _lock(session: AsyncSession, user_id: int, sid: int) -> Saving:
    s = await session.scalar(select(Saving).where(Saving.id == sid).with_for_update().execution_options(populate_existing=True))
    if s is None or s.user_id != user_id:
        raise NotFound("Jamg'arma")
    return s


def bonus_ready(s: Saving, min_days: int) -> bool:
    return bool(s.half_at and s.half_at <= _now() - timedelta(days=min_days))


def view(s: Saving, cfg: dict) -> dict:
    ready = bonus_ready(s, cfg["min_days"])
    return {"id": s.id, "title": s.title, "package_id": s.package_id, "player_id": s.player_id, "zone_id": s.zone_id,
            "target": s.target, "saved": s.saved, "weekly": s.weekly, "status": s.status, "pct": min(100, s.saved * 100 // max(1, s.target)),
            "next_at": s.next_at.isoformat() if s.next_at else None, "buy_at": s.buy_at.isoformat() if s.buy_at else None,
            "bonus_pct": cfg["bonus"], "bonus_ready": ready, "bonus_amount": s.target * cfg["bonus"] // 100 if ready else 0,
            "bonus_in_days": max(0, cfg["min_days"] - (_now() - s.half_at).days) if s.half_at and not ready else None,
            "bonus": s.bonus, "order_id": s.order_id, "created_at": s.created_at.isoformat() if s.created_at else None}


async def _deposit(session: AsyncSession, s: Saving, amount: int) -> int:
    amount = min(amount, s.target - s.saved)
    if amount <= 0:
        return 0
    s.deposits = (s.deposits or 0) + 1
    await wallet.debit(session, s.user_id, amount, "saving_in", f"saving:{s.id}:in:{s.deposits}", ref_type="saving", ref_id=s.id)
    s.saved += amount
    if s.half_at is None and s.saved * 2 >= s.target:
        s.half_at = _now()
    return amount


async def create(session: AsyncSession, user_id: int, package_id: int, player_id: str, zone_id: str,
                 weekly: int, first: int, buy_at: datetime | None) -> Saving:
    cfg = await _settings(session)
    if not cfg["on"]:
        raise BadState("Jamg'arma hozircha yopiq")
    pkg = await session.get(DonatePackage, package_id)
    if pkg is None or not pkg.is_active:
        raise NotFound("Paket")
    n = await session.scalar(select(func.count()).select_from(Saving).where(Saving.user_id == user_id, Saving.status == "active"))
    if (n or 0) >= MAX_ACTIVE:
        raise BadState(f"Bir vaqtda {MAX_ACTIVE} tadan ko'p jamg'arma ochib bo'lmaydi")
    if pkg.delivery != "voucher" and not re.fullmatch(r"[0-9A-Za-z_\-]{3,32}", (player_id or "").strip()):
        raise AppError("bad_id", "O'yin ID'sini to'g'ri kiriting")
    if weekly and weekly < 1_000:
        raise AppError("bad_amount", "Haftalik summa kamida 1 000 so'm")
    if buy_at and buy_at <= _now():
        raise AppError("bad_date", "Xarid sanasi kelajakda bo'lsin")
    s = Saving(user_id=user_id, title=pkg.name[:120], package_id=pkg.id, player_id=(player_id or "").strip()[:64],
               zone_id=(zone_id or "").strip()[:64], target=pkg.price, saved=0, deposits=0, weekly=max(0, weekly),
               next_at=_now() + timedelta(days=7) if weekly else None, buy_at=buy_at, status="active", bonus=0)
    session.add(s)
    await session.flush()
    if first > 0:
        await _deposit(session, s, first)
    return s


async def deposit(session: AsyncSession, user_id: int, sid: int, amount: int) -> Saving:
    s = await _lock(session, user_id, sid)
    if s.status != "active":
        raise BadState("Jamg'arma yakunlangan")
    if amount < 1_000:
        raise AppError("bad_amount", "Kamida 1 000 so'm")
    if not await _deposit(session, s, amount):
        raise BadState("Maqsadga yetilgan — sotib olishingiz mumkin")
    return s


async def cancel(session: AsyncSession, user_id: int, sid: int) -> Saving:
    s = await _lock(session, user_id, sid)
    if s.status != "active":
        raise BadState("Jamg'arma yakunlangan")
    if s.saved > 0:
        await wallet.credit(session, user_id, s.saved, "saving_out", f"saving:{s.id}:cancel", ref_type="saving", ref_id=s.id)
    s.status, s.finished_at = "cancelled", _now()
    return s


async def buy(session: AsyncSession, user_id: int, sid: int) -> DonateOrder:
    """Yig'ilgan pul (+ bonus) bilan buyurtma. Paket narxi oshgan bo'lsa farq hamyondan olinadi."""
    from app.services import donate

    s = await _lock(session, user_id, sid)
    if s.status != "active":
        raise BadState("Jamg'arma yakunlangan")
    if s.saved < s.target:
        raise BadState("Hali maqsadga yetilmagan")
    cfg = await _settings(session)
    bonus = s.target * cfg["bonus"] // 100 if bonus_ready(s, cfg["min_days"]) else 0
    await wallet.credit(session, user_id, s.saved, "saving_out", f"saving:{s.id}:out", ref_type="saving", ref_id=s.id)
    if bonus > 0:
        await wallet.credit(session, user_id, bonus, "saving_bonus", f"saving:{s.id}:bonus", ref_type="saving", ref_id=s.id)
    order = await donate.create_order(session, user_id, s.package_id, s.player_id, s.zone_id)
    s.status, s.finished_at, s.order_id, s.bonus = "done", _now(), order.id, bonus
    return order


async def tick(sessions: async_sessionmaker, out: Outbox) -> list[int]:
    """Haftalik avto-yig'ish va belgilangan kuni avto-xarid. Yaratilgan donat buyurtmalari ID'lari."""
    now = _now()
    orders: list[int] = []
    async with sessions() as session:
        ids = list(await session.scalars(select(Saving.id).where(
            Saving.status == "active", ((Saving.weekly > 0) & (Saving.next_at <= now)) | (Saving.buy_at <= now))))
    for sid in ids:
        async with sessions() as session:
            async with session.begin():
                s = await session.scalar(select(Saving).where(Saving.id == sid).with_for_update())
                if s is None or s.status != "active":
                    continue
                if s.weekly and s.next_at and s.next_at <= now and s.saved < s.target:
                    try:
                        async with session.begin_nested():
                            got = await _deposit(session, s, s.weekly)
                        s.next_at = now + timedelta(days=7)
                        if got and s.saved >= s.target:
                            out.user(s.user_id, f"🎯 «{s.title}» jamg'armasi to'ldi! Endi sotib olishingiz mumkin.", webapp_button("Jamg'arma", "/savings"))
                    except InsufficientFunds:
                        await session.refresh(s)
                        s.next_at = now + timedelta(days=1)
                        out.user(s.user_id, f"⚠️ «{s.title}» jamg'armasiga haftalik {fmt(s.weekly)} o'tkazib bo'lmadi — hamyonda yetarli emas.",
                                 webapp_button("Hamyon", "/wallet"))
                if s.buy_at and s.buy_at <= now:
                    if s.saved >= s.target:
                        try:
                            async with session.begin_nested():
                                order = await buy(session, s.user_id, s.id)
                            orders.append(order.id)
                            out.user(s.user_id, f"🛒 Belgilangan kun keldi: «{s.title}» sotib olindi" + (f" (+{fmt(s.bonus)} bonus)" if s.bonus else "") + ".",
                                     webapp_button("Tarix", "/history"))
                        except AppError as e:
                            await session.refresh(s)
                            s.buy_at = None
                            out.user(s.user_id, f"⚠️ «{s.title}» avtomatik sotib olinmadi: {e.message}", webapp_button("Jamg'arma", "/savings"))
                    else:
                        s.buy_at = None
                        out.user(s.user_id, f"⚠️ «{s.title}»: xarid kuni keldi, lekin maqsadga hali {fmt(s.target - s.saved)} yetmaydi.",
                                 webapp_button("Jamg'arma", "/savings"))
    return orders


async def overview(session: AsyncSession, user_id: int) -> dict:
    cfg = await _settings(session)
    rows = await session.scalars(select(Saving).where(Saving.user_id == user_id).order_by(Saving.status != "active", Saving.id.desc()).limit(30))
    items = [view(s, cfg) for s in rows]
    return {"enabled": cfg["on"], "bonus_pct": cfg["bonus"], "min_days": cfg["min_days"], "items": items,
            "total_saved": sum(i["saved"] for i in items if i["status"] == "active")}
