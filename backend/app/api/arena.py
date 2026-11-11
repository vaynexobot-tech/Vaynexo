"""Arena: ball, vazifalar, almashtirish, prognoz, jamoa topish, sezon reytingi (+ admin)."""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, SessionDep, rate_limit
from app.errors import BadState, NotFound
from app.models import Prediction, PredictionMatch, TeamPost, Tournament, TournamentEntry, User
from app.services import app_settings, arena
from app.services.notify import Outbox

router = APIRouter(tags=["arena"])


def _now():
    return datetime.now(timezone.utc)


def match_dict(m: PredictionMatch, pick: str | None = None, counts: dict | None = None) -> dict:
    return {"id": m.id, "title": m.title, "team_a": m.team_a, "team_b": m.team_b, "starts_at": m.starts_at.isoformat(),
            "status": m.status, "result": m.result, "my_pick": pick, "votes": counts or {}}


def post_dict(p: TeamPost, u: User | None, me: int) -> dict:
    return {"id": p.id, "kind": p.kind, "name": p.name, "lane": p.lane, "rank": p.rank, "online": p.online, "note": p.note,
            "expires_at": p.expires_at.isoformat(), "created_at": p.created_at.isoformat() if p.created_at else None,
            "mine": p.user_id == me, "username": u.username if u else None}


@router.get("/arena/summary")
async def summary(user: CurrentUser, session: SessionDep):
    async with session.begin():
        await arena.bump(session, user.id, "login")  # «Ilovaga kirish» vazifasi
    u = await session.get(User, user.id)
    pts = await app_settings.get_value(session, "pts_prediction")
    now = _now()
    m = await session.scalar(select(PredictionMatch).where(PredictionMatch.status == "open", PredictionMatch.starts_at > now)
                             .order_by(PredictionMatch.starts_at).limit(1))
    match = None
    if m:
        pick = await session.scalar(select(Prediction.pick).where(Prediction.match_id == m.id, Prediction.user_id == user.id))
        match = {**match_dict(m, pick), "points": pts}
    return {"points": u.points, "passes": u.tournament_passes, "vip_credit_days": u.vip_credit_days,
            "boost_coupon_percent": u.boost_coupon_percent, "prediction": match,
            "points_rules": {k: await app_settings.get_value(session, k) for k in ("pts_tournament_win", "pts_tournament_join", "pts_prediction")}}


@router.get("/arena/missions")
async def missions(user: CurrentUser, session: SessionDep):
    async with session.begin():
        await arena.bump(session, user.id, "login")
    return {**(await arena.missions(session, user.id)), "exchange": await arena.exchange_options(session),
            "points": (await session.get(User, user.id)).points}


@router.post("/arena/missions/{key}/claim")
async def claim(key: str, user: CurrentUser, session: SessionDep):
    async with session.begin():
        reward = await arena.claim(session, user.id, key)
    return {"reward": reward, "points": (await session.get(User, user.id)).points}


@router.post("/arena/exchange/{key}")
async def exchange(key: str, user: CurrentUser, session: SessionDep):
    await rate_limit(f"exch:{user.id}", limit=5, window=60)
    async with session.begin():
        u = await arena.exchange(session, user.id, key)
    return {"points": u.points, "passes": u.tournament_passes, "vip_credit_days": u.vip_credit_days,
            "boost_coupon_percent": u.boost_coupon_percent}


@router.get("/arena/leaderboard")
async def leaderboard(user: CurrentUser, session: SessionDep):
    return await arena.leaderboard(session, user.id)


class PickIn(BaseModel):
    pick: str = Field(pattern="^(a|b)$")


@router.post("/arena/predictions/{match_id}")
async def predict(match_id: int, body: PickIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await arena.predict(session, user.id, match_id, body.pick)
    m = await session.get(PredictionMatch, match_id)
    return match_dict(m, body.pick)


@router.get("/arena/team-posts")
async def team_posts(user: CurrentUser, session: SessionDep, lane: str = ""):
    q = select(TeamPost).where(TeamPost.status == "active", TeamPost.expires_at > _now())
    if lane in arena.LANES:
        q = q.where(TeamPost.lane == lane)
    rows = list(await session.scalars(q.order_by(TeamPost.id.desc()).limit(50)))
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_({p.user_id for p in rows} or {0})))}
    return [post_dict(p, users.get(p.user_id), user.id) for p in rows]


class PostIn(BaseModel):
    kind: str = Field(pattern="^(player|team)$")
    name: str = Field(max_length=64)
    lane: str = Field("", max_length=16)
    rank: str = Field("", max_length=32)
    online: str = Field("", max_length=32)
    note: str = Field("", max_length=300)


@router.post("/arena/team-posts")
async def create_post(body: PostIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"tpost:{user.id}", limit=5, window=3600)
    async with session.begin():
        p = await arena.create_post(session, user.id, body.model_dump())
    return post_dict(p, user, user.id)


@router.post("/arena/team-posts/{pid}/close")
async def close_post(pid: int, user: CurrentUser, session: SessionDep):
    async with session.begin():
        p = await session.get(TeamPost, pid)
        if p is None or (p.user_id != user.id and not user.is_admin):
            raise NotFound("E'lon")
        p.status = "closed"
    return {"ok": True}


@router.post("/arena/team-posts/{pid}/contact")
async def contact(pid: int, user: CurrentUser, session: SessionDep):
    """«Yozish»: e'lon egasiga bot orqali xabar yuboriladi (raqam va username ochilmaydi)."""
    await rate_limit(f"tcontact:{user.id}", limit=10, window=3600)
    p = await session.get(TeamPost, pid)
    if p is None or p.status != "active":
        raise NotFound("E'lon")
    if p.user_id == user.id:
        raise BadState("Bu sizning e'loningiz")
    who = f"@{user.username}" if user.username else user.first_name
    out = Outbox()
    out.user(p.user_id, f"🤝 Jamoa topish: {who} «{p.name}» e'loningiz bo'yicha siz bilan o'ynamoqchi."
             + (f"\nYozish: https://t.me/{user.username}" if user.username else "\nUsername yo'q — u sizga botda javob kutadi."))
    await out.flush()
    return {"ok": True, "username": None}


# ---------------------------------------------------------------- admin
class MatchIn(BaseModel):
    title: str = Field(max_length=120)
    team_a: str = Field(max_length=64)
    team_b: str = Field(max_length=64)
    starts_at: datetime


@router.get("/admin/arena/matches")
async def admin_matches(admin: AdminUser, session: SessionDep):
    rows = await session.scalars(select(PredictionMatch).order_by(PredictionMatch.id.desc()).limit(50))
    return [match_dict(m) for m in rows]


@router.post("/admin/arena/matches")
async def admin_create_match(body: MatchIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        m = PredictionMatch(**body.model_dump())
        session.add(m)
    return match_dict(m)


class ResultIn(BaseModel):
    result: str = Field(pattern="^(a|b)$")


@router.post("/admin/arena/matches/{mid}/settle")
async def admin_settle(mid: int, body: ResultIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        n = await arena.settle_match(session, mid, body.result, out)
    await out.flush()
    return {"winners": n}


class WinnerIn(BaseModel):
    user_id: int


@router.post("/admin/tournaments/{t_id}/winner")
async def tournament_winner(t_id: int, body: WinnerIn, admin: AdminUser, session: SessionDep):
    """G'olibni belgilash: turnir yakunlanadi, g'olibga ball beriladi."""
    out = Outbox()
    async with session.begin():
        t = await session.get(Tournament, t_id, with_for_update=True)
        if t is None:
            raise NotFound("Turnir")
        if not await session.scalar(select(TournamentEntry.id).where(
                TournamentEntry.tournament_id == t_id, TournamentEntry.user_id == body.user_id)):
            raise BadState("Bu foydalanuvchi turnir ishtirokchisi emas")
        t.status = "finished"
        pts = int(await app_settings.get_value(session, "pts_tournament_win"))
        await arena.add_points(session, body.user_id, pts, "tournament_win", f"tour_win:{t_id}")
        out.user(body.user_id, f"🏆 Tabriklaymiz! «{t.title}» turnirida g'alaba qozondingiz. +{pts} ball")
    await out.flush()
    return {"ok": True}


# ================================================================ Hamkor dasturi
from app.models import PartnerVideo  # noqa: E402
from app.services import partner  # noqa: E402


@router.get("/partner")
async def partner_overview(user: CurrentUser, session: SessionDep):
    return await partner.overview(session, user.id)


class VideoIn(BaseModel):
    url: str = Field(min_length=8, max_length=400)


@router.post("/partner/videos")
async def partner_submit(body: VideoIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"partner:{user.id}", limit=5, window=3600)
    out = Outbox()
    async with session.begin():
        v = await partner.submit(session, user.id, body.url, out)
    await out.flush()
    return partner.video_dict(v)


@router.get("/admin/partner/videos")
async def admin_partner_videos(admin: AdminUser, session: SessionDep, status: str = "pending"):
    rows = await session.scalars(select(PartnerVideo).where(PartnerVideo.status == status).order_by(PartnerVideo.id).limit(100))
    return [{**partner.video_dict(v), "user_id": v.user_id} for v in rows]


class ReviewIn(BaseModel):
    approve: bool
    views: int = Field(0, ge=0, le=1_000_000_000)
    likes: int = Field(0, ge=0, le=1_000_000_000)
    note: str | None = Field(None, max_length=300)


@router.post("/admin/partner/videos/{vid}")
async def admin_partner_review(vid: int, body: ReviewIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        v = await partner.review(session, vid, body.approve, body.views, body.likes, body.note, out)
    await out.flush()
    return partner.video_dict(v)
