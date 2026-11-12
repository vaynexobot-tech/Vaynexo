import json

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api import schemas as S
from app.api.deps import CurrentUser, SessionDep, get_redis, rate_limit
from app.errors import AppError, NotFound
from app.models import DonateOrder, DonatePackage
from app.providers import get_provider
from app.queue import enqueue

router = APIRouter(prefix="/donate", tags=["donate"])

PACKAGES_CACHE = "donate:packages:{game}"


async def invalidate_packages_cache() -> None:
    try:
        await get_redis().delete(PACKAGES_CACHE.format(game="ML"), PACKAGES_CACHE.format(game="MC"))
    except Exception:
        pass


@router.get("/packages")
async def packages(user: CurrentUser, session: SessionDep, game: str = "ML"):
    game = "MC" if game == "MC" else "ML"
    key = PACKAGES_CACHE.format(game=game)
    try:
        cached = await get_redis().get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    rows = await session.scalars(
        select(DonatePackage).where(DonatePackage.game == game, DonatePackage.is_active.is_(True)).order_by(DonatePackage.sort, DonatePackage.price)
    )
    data = [S.package(p) for p in rows]
    for d in data:
        d.pop("sku", None)
    try:
        await get_redis().set(key, json.dumps(data), ex=120)
    except Exception:
        pass
    return data


class PlayerIn(BaseModel):
    game: str = "ML"
    player_id: str = Field(max_length=20)
    zone_id: str = Field("", max_length=10)


@router.post("/check-player")
async def check_player(body: PlayerIn, user: CurrentUser):
    await rate_limit(f"chk:{user.id}", limit=10, window=60)
    if not body.player_id.strip().isdigit():
        raise AppError("bad_player_id", "ID faqat raqamlardan iborat bo'lishi kerak")
    nick = await get_provider().check_player(body.game, body.player_id.strip(), body.zone_id.strip())
    return {"found": nick is not None, "nickname": nick or None}


class OrderIn(BaseModel):
    package_id: int
    player_id: str = Field(max_length=20)
    zone_id: str = Field("", max_length=10)


@router.post("/orders")
async def create_order(body: OrderIn, user: CurrentUser, session: SessionDep):
    from app.services.donate import create_order as svc_create

    async with session.begin():
        order = await svc_create(session, user.id, body.package_id, body.player_id, body.zone_id)
    await enqueue("fulfil_donate", order.id, "create")
    return S.donate_order(order)


@router.get("/orders/{order_id}")
async def get_order(order_id: int, user: CurrentUser, session: SessionDep):
    o = await session.get(DonateOrder, order_id)
    if o is None or o.user_id != user.id:
        raise NotFound("Buyurtma")
    return S.donate_order(o)
