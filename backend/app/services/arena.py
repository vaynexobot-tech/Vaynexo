"""Arena: ball (pulga almashtirilmaydi), vazifalar, ball almashtirish, bepul prognoz, jamoa topish, sezon reytingi."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, BadState, NotFound
from app.models import MissionCounter, PointsEntry, Prediction, PredictionMatch, TeamPost, User
from app.services import app_settings
from app.services.app_settings import MISSIONS
from app.services.notify import Outbox

SEASON_EPOCH = datetime(2026, 11, 1, tzinfo=timezone.utc)
TEAM_POST_DAYS = 7
LANES = ("Gold", "Mid", "EXP", "Jungle", "Roam")
# Har bir xizmat to'lovi "Istalgan xizmatdan foydalanish" vazifasini bajaradi
SERVICE_KINDS = {"donate", "tg_service", "boost", "deal_pay", "rent_pay", "vip", "tournament_fee"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def period_of(kind: str, at: datetime | None = None) -> str:
    at = at or _now()
    if kind == "daily":
        return at.strftime("%Y%m%d")
    y, w, _ = at.isocalendar()
    return f"{y}W{w:02d}"


# ---------------------------------------------------------------- ball
async def add_points(session: AsyncSession, user_id: int, amount: int, reason: str, idem_key: str) -> bool:
    """Idempotent: bir xil idem_key ikkinchi marta ball bermaydi. Berilsa True."""
    if amount == 0:
        return False
    res = await session.execute(
        insert(PointsEntry).values(user_id=user_id, amount=amount, reason=reason, idem_key=idem_key)
        .on_conflict_do_nothing(index_elements=["idem_key"]).returning(PointsEntry.id)
    )
    if res.scalar() is None:
        return False
    await session.execute(update(User).where(User.id == user_id).values(points=User.points + amount))
    return True


async def spend_points(session: AsyncSession, user: User, cost: int, reason: str, idem_key: str) -> None:
    if user.points < cost:
        raise AppError("no_points", "Ball yetarli emas")
    await add_points(session, user.id, -cost, reason, idem_key)


# ---------------------------------------------------------------- vazifalar
async def bump(session: AsyncSession, user_id: int, key: str, n: int = 1) -> None:
    """Vazifa hisoblagichini oshiradi (davr — kunlik yoki haftalik)."""
    if key not in MISSIONS:
        return
    per = period_of(MISSIONS[key][0])
    await session.execute(
        insert(MissionCounter).values(user_id=user_id, key=key, period=per, count=n, claimed=False)
        .on_conflict_do_update(constraint="uq_mission_counter", set_={"count": MissionCounter.count + n})
    )


async def on_payment(session: AsyncSession, user_id: int, kind: str) -> None:
    if kind in SERVICE_KINDS:
        await bump(session, user_id, "any_service")


async def missions(session: AsyncSession, user_id: int) -> dict:
    rows = {(m.key, m.period): m for m in await session.scalars(select(MissionCounter).where(MissionCounter.user_id == user_id))}
    rewards = await app_settings.get_many(session, *[f"mission_{k}" for k in MISSIONS])
    out = {"daily": [], "weekly": []}
    for key, (kind, title, goal, _) in MISSIONS.items():
        m = rows.get((key, period_of(kind)))
        out[kind].append({"key": key, "title": title, "goal": goal, "progress": min(goal, m.count if m else 0),
                          "claimed": bool(m and m.claimed), "reward": int(rewards[f"mission_{key}"])})
    return out


async def claim(session: AsyncSession, user_id: int, key: str) -> int:
    if key not in MISSIONS:
        raise NotFound("Vazifa")
    kind, _, goal, _ = MISSIONS[key]
    per = period_of(kind)
    m = await session.scalar(select(MissionCounter).where(
        MissionCounter.user_id == user_id, MissionCounter.key == key, MissionCounter.period == per).with_for_update())
    if m is None or m.count < goal:
        raise BadState("Vazifa hali bajarilmagan")
    if m.claimed:
        raise BadState("Mukofot allaqachon olingan")
    m.claimed = True
    reward = int(await app_settings.get_value(session, f"mission_{key}"))
    await add_points(session, user_id, reward, "mission", f"mission:{user_id}:{key}:{per}")
    return reward


# ---------------------------------------------------------------- ball almashtirish
async def exchange_options(session: AsyncSession) -> list[dict]:
    s = await app_settings.get_many(session, "ex_boost_discount_cost", "ex_boost_discount_percent", "ex_vip_3d_cost",
                                    "ex_free_tournament_cost")
    return [
        {"key": "boost_discount", "title": f"Boost'ga {s['ex_boost_discount_percent']}% chegirma", "cost": s["ex_boost_discount_cost"]},
        {"key": "vip_3d", "title": "VIP e'lon · 3 kun", "cost": s["ex_vip_3d_cost"]},
        {"key": "free_tournament", "title": "Turnirga bepul kirish", "cost": s["ex_free_tournament_cost"]},
    ]


async def exchange(session: AsyncSession, user_id: int, key: str) -> User:
    opts = {o["key"]: o for o in await exchange_options(session)}
    if key not in opts:
        raise NotFound("Almashtirish")
    user = await session.get(User, user_id, with_for_update=True)
    if key == "boost_discount" and user.boost_coupon_percent > 0:
        raise BadState("Sizda ishlatilmagan Boost chegirmasi bor")
    n = await session.scalar(select(func.count()).select_from(PointsEntry).where(PointsEntry.user_id == user_id))
    await spend_points(session, user, int(opts[key]["cost"]), f"exchange_{key}", f"exchange:{user_id}:{key}:{n}")
    if key == "boost_discount":
        user.boost_coupon_percent = int(await app_settings.get_value(session, "ex_boost_discount_percent"))
    elif key == "vip_3d":
        user.vip_credit_days += 3
    else:
        user.tournament_passes += 1
    return user


# ---------------------------------------------------------------- sezon reytingi
async def season(session: AsyncSession) -> dict:
    days = int(await app_settings.get_value(session, "season_days"))
    n = int((_now() - SEASON_EPOCH).total_seconds() // (days * 86400)) + 1
    start = SEASON_EPOCH + timedelta(days=days * (n - 1))
    return {"number": n, "start": start, "end": start + timedelta(days=days), "days": days}


async def leaderboard(session: AsyncSession, user_id: int, limit: int = 100) -> dict:
    s = await season(session)
    earned = func.sum(PointsEntry.amount).label("pts")
    q = (select(PointsEntry.user_id, earned).where(PointsEntry.amount > 0, PointsEntry.created_at >= s["start"])
         .group_by(PointsEntry.user_id).order_by(earned.desc(), PointsEntry.user_id))
    rows = (await session.execute(q.limit(limit))).all()
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_([r[0] for r in rows] or [0])))}
    items = [{"place": i + 1, "user_id": uid, "name": (users[uid].username or users[uid].first_name) if uid in users else "—",
              "points": int(p)} for i, (uid, p) in enumerate(rows)]
    mine = next((x for x in items if x["user_id"] == user_id), None)
    if mine is None:
        my_pts = await session.scalar(select(func.coalesce(func.sum(PointsEntry.amount), 0)).where(
            PointsEntry.user_id == user_id, PointsEntry.amount > 0, PointsEntry.created_at >= s["start"])) or 0
        sq = q.subquery()
        above = await session.scalar(select(func.count()).select_from(sq).where(sq.c.pts > my_pts)) if my_pts else None
        mine = {"place": (above or 0) + 1 if my_pts else None, "user_id": user_id, "name": "", "points": int(my_pts)}
    week = await session.scalar(select(func.coalesce(func.sum(PointsEntry.amount), 0)).where(
        PointsEntry.user_id == user_id, PointsEntry.amount > 0, PointsEntry.created_at >= _now() - timedelta(days=7))) or 0
    return {"season": {"number": s["number"], "ends_at": s["end"].isoformat(),
                       "days_left": max(0, (s["end"] - _now()).days)}, "items": items, "me": mine, "week": int(week)}


# ---------------------------------------------------------------- bepul prognoz
async def predict(session: AsyncSession, user_id: int, match_id: int, pick: str) -> Prediction:
    if pick not in ("a", "b"):
        raise AppError("bad_pick", "Jamoani tanlang")
    m = await session.get(PredictionMatch, match_id)
    if m is None:
        raise NotFound("O'yin")
    if m.status != "open" or m.starts_at <= _now():
        raise BadState("Prognoz qabul qilish yopilgan")
    p = Prediction(match_id=match_id, user_id=user_id, pick=pick)
    session.add(p)
    try:
        await session.flush()
    except IntegrityError as e:
        raise BadState("Siz allaqachon prognoz qilgansiz") from e
    return p


async def settle_match(session: AsyncSession, match_id: int, result: str, out: Outbox) -> int:
    if result not in ("a", "b"):
        raise AppError("bad_result", "Natijani tanlang")
    m = await session.get(PredictionMatch, match_id, with_for_update=True)
    if m is None:
        raise NotFound("O'yin")
    if m.status == "settled":
        raise BadState("Natija allaqachon kiritilgan")
    m.status, m.result = "settled", result
    pts = int(await app_settings.get_value(session, "pts_prediction"))
    winner = m.team_a if result == "a" else m.team_b
    n = 0
    for p in await session.scalars(select(Prediction).where(Prediction.match_id == match_id, Prediction.pick == result)):
        if await add_points(session, p.user_id, pts, "prediction", f"prediction:{match_id}:{p.user_id}"):
            n += 1
            out.user(p.user_id, f"🎯 Prognozingiz to'g'ri chiqdi: {winner} g'alaba qildi! +{pts} ball", kind="tour")
    return n


# ---------------------------------------------------------------- jamoa topish
def validate_post(data: dict) -> dict:
    kind = data.get("kind")
    if kind not in ("player", "team"):
        raise AppError("bad_kind", "O'yinchi yoki jamoa ekanini tanlang")
    name = (data.get("name") or "").strip()[:64]
    if len(name) < 2:
        raise AppError("bad_name", "Nik yoki jamoa nomini kiriting")
    lane = data.get("lane") or ""
    if lane and lane not in LANES:
        raise AppError("bad_lane", "Liniya noto'g'ri")
    return {"kind": kind, "name": name, "lane": lane, "rank": (data.get("rank") or "").strip()[:32],
            "online": (data.get("online") or "").strip()[:32], "note": (data.get("note") or "").strip()[:300]}


async def create_post(session: AsyncSession, user_id: int, data: dict) -> TeamPost:
    active = await session.scalar(select(func.count()).select_from(TeamPost).where(
        TeamPost.user_id == user_id, TeamPost.status == "active", TeamPost.expires_at > _now()))
    if active >= 2:
        raise AppError("too_many", "Bir vaqtda 2 tadan ko'p e'lon joylab bo'lmaydi")
    post = TeamPost(user_id=user_id, expires_at=_now() + timedelta(days=TEAM_POST_DAYS), **validate_post(data))
    session.add(post)
    await session.flush()
    return post
