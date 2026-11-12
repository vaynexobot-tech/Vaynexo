"""Statistika: kunlik hisobot (guruhga) va admin paneldagi grafik."""

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BoostOrder, Deal, DonateOrder, LedgerEntry, Rental, TgOrder, Topup, User, Withdrawal,
)

log = logging.getLogger(__name__)
TZ = ZoneInfo("Asia/Tashkent")
REPORT_HOUR = 9  # har kuni 09:00 (Toshkent)
REPORT_KEY = "_daily_report_date"


def _day(col):
    return func.date(func.timezone(literal_column("'Asia/Tashkent'"), col))


async def _series(session: AsyncSession, col, amount, *where) -> dict[date, int]:
    rows = (await session.execute(select(_day(col), func.coalesce(func.sum(amount), 0)).where(*where).group_by(_day(col)))).all()
    return {d: int(v) for d, v in rows}


async def analytics(session: AsyncSession, days: int = 30) -> dict:
    """Kunlik qatorlar: aylanma va platforma daromadi (komissiya + boost ulushi)."""
    days = max(1, min(days, 90))
    start_day = datetime.now(TZ).date() - timedelta(days=days - 1)
    since = datetime.combine(start_day, datetime.min.time(), TZ)
    s = {
        "topup": await _series(session, Topup.paid_at, Topup.pay_amount, Topup.status == "paid", Topup.paid_at >= since),
        "donate": await _series(session, DonateOrder.created_at, DonateOrder.price, DonateOrder.status == "done", DonateOrder.created_at >= since),
        "tg": await _series(session, TgOrder.created_at, TgOrder.price, TgOrder.status == "done", TgOrder.created_at >= since),
        "deals": await _series(session, Deal.created_at, Deal.price, Deal.status == "completed", Deal.created_at >= since),
        "deal_fee": await _series(session, Deal.created_at, Deal.commission, Deal.status == "completed", Deal.created_at >= since),
        "rent_fee": await _series(session, Rental.created_at, Rental.commission, Rental.status == "completed", Rental.created_at >= since),
        "boost": await _series(session, BoostOrder.created_at, BoostOrder.price, BoostOrder.status == "done", BoostOrder.created_at >= since),
        "boost_paid": await _series(session, LedgerEntry.created_at, LedgerEntry.amount, LedgerEntry.kind == "boost_payout", LedgerEntry.created_at >= since),
        "withdraw": await _series(session, Withdrawal.created_at, Withdrawal.amount, Withdrawal.status == "paid", Withdrawal.created_at >= since),
        "users": await _series(session, User.created_at, 1, User.created_at >= since),
    }
    out = []
    for i in range(days):
        d = start_day + timedelta(days=i)
        g = {k: v.get(d, 0) for k, v in s.items()}
        income = g["deal_fee"] + g["rent_fee"] + max(0, g["boost"] - g["boost_paid"])
        out.append({"date": d.isoformat(), "topup": g["topup"], "turnover": g["donate"] + g["tg"] + g["deals"] + g["boost"],
                    "donate": g["donate"], "tg": g["tg"], "deals": g["deals"], "boost": g["boost"],
                    "income": income, "withdraw": g["withdraw"], "users": g["users"]})
    top = (await session.execute(
        select(DonateOrder.title, func.count(), func.sum(DonateOrder.price))
        .where(DonateOrder.status == "done", DonateOrder.created_at >= since)
        .group_by(DonateOrder.title).order_by(func.count().desc()).limit(5)
    )).all()
    tot = {k: sum(x[k] for x in out) for k in ("topup", "turnover", "income", "withdraw", "users", "donate", "tg", "deals", "boost")}
    return {"days": out, "total": tot, "top_packages": [{"title": t, "count": c, "sum": int(v or 0)} for t, c, v in top]}


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


async def daily_text(session: AsyncSession) -> str:
    a = await analytics(session, 2)
    y = a["days"][0]  # kecha
    total_users = await session.scalar(select(func.count()).select_from(User)) or 0
    balances = await session.scalar(select(func.coalesce(func.sum(User.balance), 0))) or 0
    d = datetime.fromisoformat(y["date"]).strftime("%d.%m.%Y")
    return (
        f"📊 Kunlik hisobot · {d}\n\n"
        f"💳 To'ldirildi: {fmt(y['topup'])} so'm\n"
        f"🔄 Aylanma: {fmt(y['turnover'])} so'm\n"
        f"   💎 Donat {fmt(y['donate'])} · ⭐️ TG {fmt(y['tg'])}\n"
        f"   🛒 Akkaunt {fmt(y['deals'])} · 🚀 Boost {fmt(y['boost'])}\n"
        f"💰 Platforma daromadi: {fmt(y['income'])} so'm\n"
        f"💸 Yechildi: {fmt(y['withdraw'])} so'm\n"
        f"👥 Yangi foydalanuvchi: {y['users']} (jami {total_users})\n"
        f"🏦 Hamyonlardagi jami pul: {fmt(int(balances))} so'm"
    )


async def maybe_send_daily() -> bool:
    """Har daqiqa chaqiriladi; soat 09:00 dan keyin kuniga bir marta guruhning «hisobot» mavzusiga yuboradi."""
    from sqlalchemy.dialects.postgresql import insert

    from app.db import SessionLocal
    from app.models import AppSetting
    from app.services.notify import Outbox

    now = datetime.now(TZ)
    if now.hour < REPORT_HOUR:
        return False
    today = now.date().isoformat()
    async with SessionLocal() as s:
        if await s.scalar(select(AppSetting.value).where(AppSetting.key == REPORT_KEY)) == today:
            return False
        text = await daily_text(s)
    async with SessionLocal() as s, s.begin():
        await s.execute(insert(AppSetting).values(key=REPORT_KEY, value=today)
                        .on_conflict_do_update(index_elements=["key"], set_={"value": today}))
    out = Outbox()
    out.admins(text, topic="hisobot")
    await out.flush()
    return True
