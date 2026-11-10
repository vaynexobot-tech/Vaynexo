import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api import schemas as S
from app.api.deps import CurrentUser, SessionDep, get_redis
from app.config import settings
from app.models import BoostOrder, Deal, DonateOrder, LedgerEntry, Listing, TgOrder, Topup, Tournament, User, Withdrawal
from app.services import app_settings
from app.services.market import seller_stats


async def referral_stats(session, uid: int) -> dict:
    invited = await session.scalar(select(func.count()).select_from(User).where(User.referrer_id == uid)) or 0
    paid = await session.scalar(
        select(func.count()).select_from(User).where(User.referrer_id == uid, User.referral_paid.is_(True))
    ) or 0
    earned = await session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.user_id == uid, LedgerEntry.kind == "referral")
    ) or 0
    return {"ref_invited": invited, "ref_paid": paid, "ref_earned": int(earned)}

router = APIRouter(tags=["user"])


@router.get("/me")
async def me(user: CurrentUser, session: SessionDep):
    stats = await seller_stats(session, user.id)
    active_listings = await session.scalar(
        select(func.count()).select_from(Listing).where(Listing.seller_id == user.id, Listing.status == "active")
    )
    return {
        **S.user_private(user),
        **stats,
        "active_listings": active_listings or 0,
        "referral_bonus": await app_settings.get_value(session, "referral_bonus"),
        "referral_min_topup": await app_settings.get_value(session, "referral_min_topup"),
        **(await referral_stats(session, user.id)),
        "ref_link": f"https://t.me/{settings.bot_username}?startapp=ref_{user.id}" if settings.bot_username else None,
        "commission_percent": settings.commission_percent,
    }


class ProfileIn(BaseModel):
    first_name: str | None = Field(None, max_length=128)
    phone: str | None = Field(None, max_length=32)
    ml_id: str | None = Field(None, max_length=32)
    bio: str | None = Field(None, max_length=300)
    lang: str | None = Field(None, pattern="^(uz|ru)$")


@router.patch("/me")
async def update_me(body: ProfileIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        u = await session.get(User, user.id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(u, k, (v.strip() if isinstance(v, str) else v) or (None if k != "first_name" else u.first_name))
    return S.user_private(u)


@router.get("/home")
async def home(user: CurrentUser, session: SessionDep):
    t = await session.scalar(
        select(Tournament).where(Tournament.status == "open").order_by(Tournament.prize_fund.desc()).limit(1)
    )
    return {"balance": user.balance, "tickets": user.tickets, "tournament": S.tournament(t) if t else None}


@router.get("/top")
async def top(user: CurrentUser, session: SessionDep, period: str = "week"):
    """Top donaterlar: yakunlangan donatlar summasi bo'yicha. 5 daqiqa keshlanadi."""
    period = period if period in ("week", "month", "all") else "week"
    cache_key = f"top:{period}"
    rows = None
    try:
        cached = await get_redis().get(cache_key)
        rows = json.loads(cached) if cached else None
    except Exception:
        rows = None
    if rows is None:
        q = select(DonateOrder.user_id, func.sum(DonateOrder.price).label("total")).where(DonateOrder.status == "done")
        if period != "all":
            days = 7 if period == "week" else 30
            q = q.where(DonateOrder.created_at >= datetime.now(timezone.utc) - timedelta(days=days))
        q = q.group_by(DonateOrder.user_id).order_by(func.sum(DonateOrder.price).desc()).limit(100)
        agg = (await session.execute(q)).all()
        users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_([r[0] for r in agg])))} if agg else {}
        rows = [
            {"place": i + 1, "user_id": uid, "name": (users[uid].username or users[uid].first_name) if uid in users else "—", "total": int(total)}
            for i, (uid, total) in enumerate(agg)
        ]
        try:
            await get_redis().set(cache_key, json.dumps(rows), ex=300)
        except Exception:
            pass
    mine = next((r for r in rows if r["user_id"] == user.id), None)
    return {"period": period, "items": rows, "me": mine}


@router.get("/history")
async def history(user: CurrentUser, session: SessionDep, type: str = "all", limit: int = 50):
    """Barcha xaridlar bitta ro'yxatda (donat, akkaunt, boost, telegram, to'ldirish, yechish)."""
    limit = max(1, min(limit, 100))
    items: list[dict] = []
    uid = user.id

    if type in ("all", "donate"):
        for o in await session.scalars(select(DonateOrder).where(DonateOrder.user_id == uid).order_by(DonateOrder.id.desc()).limit(limit)):
            items.append({"type": "donate", "id": o.id, "game": o.game, "title": o.title,
                          "sub": f"ID {o.player_id}" + (f" ({o.zone_id})" if o.zone_id else ""),
                          "amount": -o.price, "status": o.status, "created_at": S.iso(o.created_at)})
    if type in ("all", "account"):
        for d in await session.scalars(select(Deal).where(Deal.buyer_id == uid).order_by(Deal.id.desc()).limit(limit)):
            items.append({"type": "account", "id": d.id, "game": d.listing.game, "title": d.listing.title,
                          "sub": "Garantli bitim", "amount": -d.price, "status": d.status, "created_at": S.iso(d.created_at)})
    if type in ("all", "boost"):
        for b in await session.scalars(select(BoostOrder).where(BoostOrder.user_id == uid).order_by(BoostOrder.id.desc()).limit(limit)):
            items.append({"type": "boost", "id": b.id, "game": b.game, "title": f"{b.current_rank} → {b.target_rank}",
                          "sub": "Rank boost", "amount": -b.price, "status": b.status, "created_at": S.iso(b.created_at)})
    if type in ("all", "telegram"):
        for t in await session.scalars(select(TgOrder).where(TgOrder.user_id == uid).order_by(TgOrder.id.desc()).limit(limit)):
            items.append({"type": "telegram", "id": t.id, "game": "TG", "title": t.title, "sub": t.target_username,
                          "amount": -t.price, "status": t.status, "created_at": S.iso(t.created_at)})
    if type in ("all", "wallet"):
        for t in await session.scalars(select(Topup).where(Topup.user_id == uid, Topup.status == "paid").order_by(Topup.id.desc()).limit(limit)):
            items.append({"type": "topup", "id": t.id, "game": "UZS", "title": "Hamyon to'ldirish", "sub": "P2P karta",
                          "amount": t.pay_amount, "status": "done", "created_at": S.iso(t.paid_at or t.created_at)})
        for w in await session.scalars(select(Withdrawal).where(Withdrawal.user_id == uid).order_by(Withdrawal.id.desc()).limit(limit)):
            items.append({"type": "withdraw", "id": w.id, "game": "UZS", "title": "Pul yechish", "sub": "•••• " + w.card_number[-4:],
                          "amount": -w.amount, "status": w.status, "created_at": S.iso(w.created_at)})

    items.sort(key=lambda x: x["created_at"] or "", reverse=True)
    items = items[:limit]
    spent = sum(-i["amount"] for i in items if i["amount"] < 0 and i["status"] in ("done", "completed"))
    return {"items": items, "spent": spent, "count": len(items)}
