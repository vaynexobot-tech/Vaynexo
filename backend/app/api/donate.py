import json

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api import schemas as S
from app.api.deps import CurrentUser, SessionDep, get_redis, rate_limit
from app.config import settings
from app.errors import AppError, NotFound
from app.models import DonateGame, DonateOrder, DonatePackage, DonateProvider
from app.providers import get_provider
from app.queue import enqueue

router = APIRouter(prefix="/donate", tags=["donate"])

PACKAGES_CACHE = "donate:packages:{game}"


async def invalidate_packages_cache() -> None:
    try:
        r = get_redis()
        keys = [k async for k in r.scan_iter(match="donate:packages:*")]
        if keys:
            await r.delete(*keys)
    except Exception:
        pass


def game_dict(g: DonateGame, available: bool) -> dict:
    fields = g.fields or ([{"key": "player_id", "label": "User ID", "placeholder": "12345678", "pattern": r"^\d{5,20}$"},
                           {"key": "server_id", "label": "Zone ID", "placeholder": "1234", "pattern": r"^\d{1,10}$"}] if g.slug in ("ML", "MC") else [])
    return {"slug": g.slug, "name": g.name, "logo": g.logo_url, "hero": g.hero_url, "category": g.category,
            "fields": fields, "available": available, "slot": g.featured_slot}


async def _games(session) -> tuple[list[DonateGame], set[str]]:
    games = list(await session.scalars(select(DonateGame).where(DonateGame.is_active.is_(True)).order_by(DonateGame.sort, DonateGame.name)))
    have = set(await session.scalars(select(DonatePackage.game).where(DonatePackage.is_active.is_(True)).distinct()))
    return games, have


@router.get("/games")
async def games(user: CurrentUser, session: SessionDep):
    """Bosh sahifa: asosiy (katta) kartalar, mashhur o'yinlar (4×2) va hammasi."""
    rows, have = await _games(session)
    d = [game_dict(g, g.slug in have) for g in rows]
    featured = sorted((x for x in d if x["slot"]), key=lambda x: x["slot"])[:3]
    popular = [game_dict(g, g.slug in have) for g in rows if g.popular and not g.featured_slot][:8]
    return {"featured": featured, "popular": popular, "all": d}


@router.get("/games/{slug}")
async def game_info(slug: str, user: CurrentUser, session: SessionDep):
    g = await session.get(DonateGame, slug)
    if g is None or not g.is_active:
        raise NotFound("O'yin")
    _, have = await _games(session)
    return game_dict(g, g.slug in have)


@router.get("/packages")
async def packages(user: CurrentUser, session: SessionDep, game: str = "ML"):
    g = await session.get(DonateGame, game)
    if g is None or not g.is_active:
        raise NotFound("O'yin")
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
        d.pop("cost_usd", None)
    try:
        await get_redis().set(key, json.dumps(data), ex=120)
    except Exception:
        pass
    return data


class PlayerIn(BaseModel):
    game: str = "ML"
    player_id: str = Field(max_length=64)
    zone_id: str = Field("", max_length=64)


@router.post("/check-player")
async def check_player(body: PlayerIn, user: CurrentUser, session: SessionDep):
    from app.services.donate import ID_RE, _safe_match
    from app.services.donate_catalog import provider_for_game

    await rate_limit(f"chk:{user.id}", limit=10, window=60)
    g = await session.get(DonateGame, body.game)
    if g is None or not g.is_active:
        raise NotFound("O'yin")
    pid = body.player_id.strip()
    first = (g.fields or [{}])[0] if g.fields else ({"pattern": r"^\d{5,20}$"} if g.slug in ("ML", "MC") else {})
    if not ID_RE.match(pid) or (first.get("pattern") and not _safe_match(first["pattern"], pid)):
        raise AppError("bad_player_id", "ID noto'g'ri kiritilgan")
    prov = await provider_for_game(session, g)
    await session.rollback()  # tashqi so'rov paytida bazani band qilmaymiz
    nick = await prov.check_player(g.brand_slug or g.slug, pid, body.zone_id.strip())
    return {"found": nick is not None, "nickname": nick or None}


class OrderIn(BaseModel):
    package_id: int
    player_id: str = Field(max_length=64)
    zone_id: str = Field("", max_length=64)


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


# ------------------------------------------------------------------ Yupay vebhuki
webhook_router = APIRouter(prefix="/yupay", tags=["yupay"])


def verify_yupay_signature(headers, body: bytes, api_key: str, now: float | None = None) -> bool:
    """HMAC-SHA256(API kalit, timestamp\ndelivery\nevent\nsha256(body)) — hujjatdagi sxema."""
    import hashlib
    import hmac
    import time

    ts = headers.get("x-yupay-timestamp", "")
    canonical = "\n".join((ts, headers.get("x-yupay-delivery", ""), headers.get("x-yupay-event", ""),
                           hashlib.sha256(body).hexdigest())).encode()
    expected = hmac.new(api_key.encode(), canonical, hashlib.sha256).hexdigest()
    sent = [x.strip() for x in headers.get("x-yupay-key-signature", "").split(",") if x.strip()]
    if not api_key or not any(hmac.compare_digest(expected, x) for x in sent):
        return False
    return ts.isdigit() and abs((now or time.time()) - int(ts)) <= 300


async def _handle_webhook(request: Request, api_key: str) -> dict:
    import re

    body = (await request.body())[:20_000]
    if not verify_yupay_signature(request.headers, body, api_key):
        raise AppError("bad_signature", "Imzo noto'g'ri", 401)
    try:
        data = json.loads(body)
    except ValueError:
        return {"ok": True}
    if request.headers.get("x-yupay-event") == "order.status_changed":
        m = re.fullmatch(r"VX-D(\d+)", str(data.get("merchant_order_id", "")))
        if m:
            await enqueue("fulfil_donate", int(m.group(1)), "check")
    return {"ok": True}


@webhook_router.post("/webhook")
async def yupay_webhook(request: Request):
    """Render'dagi eski sozlama (DONATE_PROVIDER_KEY) uchun."""
    return await _handle_webhook(request, settings.donate_provider_key)


@webhook_router.post("/webhook/{provider_id}")
async def yupay_webhook_provider(provider_id: int, request: Request, session: SessionDep):
    """Admin paneldan qo'shilgan provayder uchun (kalit bazadan, shifrdan ochiladi)."""
    from app.security import decrypt

    row = await session.get(DonateProvider, provider_id)
    if row is None or row.kind != "yupay":
        raise NotFound("Provayder")
    key = decrypt(row.key_enc) or ""
    await session.rollback()
    return await _handle_webhook(request, key)
