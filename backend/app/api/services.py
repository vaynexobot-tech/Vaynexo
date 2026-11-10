from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api import schemas as S
from app.api.deps import CurrentUser, SessionDep
from app.errors import NotFound
from app.models import BoostOrder, TgOrder, Tournament, TournamentEntry
from app.queue import enqueue
from app.services import catalog
from app.services import services as svc
from app.services.notify import Outbox

router = APIRouter(tags=["services"])


# ------------------------------------------------------------------ Telegram
@router.get("/tg/catalog")
async def tg_catalog(user: CurrentUser):
    return catalog.public_catalog()


class TgOrderIn(BaseModel):
    kind: str
    target_username: str = Field("", max_length=64)
    for_self: bool = False
    months: int | None = None
    stars: int | None = None
    gift: str | None = None
    nft: str | None = None
    message: str = Field("", max_length=200)
    anonymous: bool = False
    link: str = Field("", max_length=200)
    note: str = Field("", max_length=300)


@router.post("/tg/orders")
async def tg_order(body: TgOrderIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        o = await svc.create_tg_order(session, user, body.model_dump(), out)
    await out.flush()
    return S.tg_order(o)


@router.get("/tg/orders/{order_id}")
async def tg_order_get(order_id: int, user: CurrentUser, session: SessionDep):
    o = await session.get(TgOrder, order_id)
    if o is None or o.user_id != user.id:
        raise NotFound("Buyurtma")
    return S.tg_order(o)


# ------------------------------------------------------------------ Boost
class BoostIn(BaseModel):
    game: str = "ML"
    current_rank: str
    current_division: str = "V"
    current_stars: int = Field(0, ge=0, le=1000)
    target_rank: str
    target_stars: int = Field(0, ge=0, le=1000)
    lane: str = ""
    hero: str = Field("", max_length=32)
    express: bool = False
    note: str = Field("", max_length=500)
    login_method: str = "telegram"
    credentials: str = Field("", max_length=500)


@router.post("/boost/quote")
async def boost_quote(body: BoostIn, user: CurrentUser, session: SessionDep):
    return svc.boost_quote(body.model_dump(), await svc.boost_percents(session))


@router.post("/boost/orders")
async def boost_create(body: BoostIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        o = await svc.create_boost(session, user, body.model_dump(), out)
    await out.flush()
    await enqueue("post_boost", o.id)  # boosterlar guruhiga e'lon
    return S.boost(o)


@router.get("/boost/orders")
async def boost_list(user: CurrentUser, session: SessionDep):
    rows = await session.scalars(select(BoostOrder).where(BoostOrder.user_id == user.id).order_by(BoostOrder.id.desc()).limit(50))
    return [S.boost(o) for o in rows]


@router.get("/boost/orders/{order_id}")
async def boost_get(order_id: int, user: CurrentUser, session: SessionDep):
    o = await session.get(BoostOrder, order_id)
    if o is None or o.user_id != user.id:
        raise NotFound("Buyurtma")
    return S.boost(o)


class BoostActionIn(BaseModel):
    reason: str = Field("", max_length=300)


@router.post("/boost/orders/{order_id}/{action}")
async def boost_action(order_id: int, action: str, body: BoostActionIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        o = await svc.boost_client_action(session, order_id, user.id, action, body.reason, out)
    await out.flush()
    if action == "cancel":
        await enqueue("update_boost_post", o.id)
    return S.boost(o)


# ------------------------------------------------------------------ Arena
@router.get("/tournaments")
async def tournaments(user: CurrentUser, session: SessionDep, status: str = "open"):
    status = status if status in ("open", "running", "finished") else "open"
    rows = list(await session.scalars(select(Tournament).where(Tournament.status == status).order_by(Tournament.starts_at).limit(50)))
    joined = set(
        await session.scalars(
            select(TournamentEntry.tournament_id).where(
                TournamentEntry.user_id == user.id, TournamentEntry.tournament_id.in_([t.id for t in rows] or [0])
            )
        )
    )
    return [S.tournament(t, t.id in joined) for t in rows]


@router.get("/tournaments/{t_id}")
async def tournament(t_id: int, user: CurrentUser, session: SessionDep):
    t = await session.get(Tournament, t_id)
    if t is None:
        raise NotFound("Turnir")
    joined = await session.scalar(
        select(TournamentEntry.id).where(TournamentEntry.tournament_id == t_id, TournamentEntry.user_id == user.id)
    )
    return S.tournament(t, bool(joined))


class JoinIn(BaseModel):
    nick: str = Field(max_length=64)
    game_id: str = Field(max_length=32)
    server: str = Field("", max_length=16)
    tg_username: str = Field("", max_length=64)


@router.post("/tournaments/{t_id}/join")
async def join(t_id: int, body: JoinIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await svc.join_tournament(session, t_id, user.id, body.model_dump())
        t = await session.get(Tournament, t_id)
    return S.tournament(t, True)
