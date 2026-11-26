import json

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

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


ETA_MIN_SAMPLES = 5  # kamida shuncha yetkazilgan buyurtma bo'lsa — vaqt ko'rsatiladi (aks holda taxmin qilinmaydi)


async def delivery_eta(session, slug: str) -> int | None:
    """Oxirgi 20 ta avtomatik yetkazilgan buyurtmaning mediana vaqti (soniya). Qo'lda bajarilganlar hisobga olinmaydi."""
    import statistics

    from sqlalchemy import func

    secs = [float(x) for x in await session.scalars(
        select(func.extract("epoch", DonateOrder.finished_at - DonateOrder.created_at))
        .join(DonatePackage, DonatePackage.id == DonateOrder.package_id)
        .where(DonateOrder.game == slug, DonateOrder.status == "done", DonateOrder.finished_at.is_not(None),
               DonatePackage.provider_id.is_not(None), DonateOrder.attempts > 0)
        .order_by(DonateOrder.id.desc()).limit(20))]
    return int(statistics.median(secs)) if len(secs) >= ETA_MIN_SAMPLES else None


def game_dict(g: DonateGame, available: bool) -> dict:
    fields = g.fields or ([{"key": "player_id", "label": "User ID", "placeholder": "12345678", "pattern": r"^\d{5,20}$"},
                           {"key": "server_id", "label": "Zone ID", "placeholder": "1234", "pattern": r"^\d{1,10}$"}] if g.slug in ("ML", "MC") else [])
    logo = f"/api/donate/game-image/{g.slug}?v={g.image_ver}" if g.image_ver else g.logo_url
    return {"slug": g.slug, "name": g.name, "logo": logo, "hero": None if g.image_ver else g.hero_url, "category": g.category,
            "voucher": not g.fields and g.slug not in ("ML", "MC"),
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


@router.get("/game-image/{slug}")
async def game_image(slug: str, session: SessionDep):
    """O'yin rasmi (ochiq: <img> tegi sarlavha yubormaydi). Versiya parametri bilan uzoq keshlanadi."""
    from fastapi import Response
    from sqlalchemy.orm import undefer

    g = await session.scalar(select(DonateGame).options(undefer(DonateGame.image)).where(DonateGame.slug == slug))
    if g is None or not g.image:
        raise NotFound("Rasm")
    return Response(g.image, media_type="image/webp", headers={"Cache-Control": "public, max-age=604800, immutable"})


@router.get("/games/{slug}")
async def game_info(slug: str, user: CurrentUser, session: SessionDep):
    g = await session.get(DonateGame, slug)
    if g is None or not g.is_active:
        raise NotFound("O'yin")
    _, have = await _games(session)
    return {**game_dict(g, g.slug in have), "eta_seconds": await delivery_eta(session, g.slug)}


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
    q = select(DonatePackage).where(DonatePackage.game == game, DonatePackage.is_active.is_(True))
    if g.provider_id:  # bir o'yinda bir nechta API bo'lishi mumkin — faqat tanlangani ko'rinadi (+ qo'lda kiritilganlar)
        q = q.where(or_(DonatePackage.provider_id == g.provider_id, DonatePackage.provider_id.is_(None)))
    rows = await session.scalars(q.order_by(DonatePackage.sort, DonatePackage.price))
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
    from app.services.donate import order_voucher

    return {**S.donate_order(o), "voucher": order_voucher(o)}


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
        mo = str(data.get("merchant_order_id", ""))
        m = re.fullmatch(r"VX-D(\d+)", mo)
        if m:
            await enqueue("fulfil_donate", int(m.group(1)), "check")
        t = re.fullmatch(r"VX-T(\d+)", mo)
        if t:
            await enqueue("fulfil_tg", int(t.group(1)), "check")
    return {"ok": True}


fazer_webhook_router = APIRouter(prefix="/fazercards", tags=["fazercards"])


def verify_fazer_signature(headers, body: bytes, secret: str) -> bool:
    """X-Webhook-Signature: sha256=<hex HMAC-SHA256(xom tana, vebhuk siri)> (FazerCards hujjati)."""
    import hashlib
    import hmac

    if not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(headers.get("x-webhook-signature", ""), expected)


@fazer_webhook_router.post("/webhook/{provider_id}")
async def fazer_webhook(provider_id: int, request: Request, session: SessionDep):
    """FazerCards buyurtma holati o'zgardi. Tanada kod yo'q va bizning ID yo'q: ularning ID'si (`ord-N`) bo'yicha topamiz,
    keyin holatni o'zimiz so'raymiz. Vebhuk kelmasa ham navbat o'zi so'rab turadi."""
    import re

    from app.security import decrypt

    row = await session.get(DonateProvider, provider_id)
    if row is None or row.kind != "fazercards":
        raise NotFound("Provayder")
    secret = decrypt((row.config or {}).get("webhook_secret_enc") or "") or ""
    await session.rollback()
    body = (await request.body())[:20_000]
    if not verify_fazer_signature(request.headers, body, secret):
        raise AppError("bad_signature", "Imzo noto'g'ri", 401)
    try:
        data = json.loads(body)
    except ValueError:
        return {"ok": True}
    oid = str((data.get("data") or {}).get("order_id") or "") if isinstance(data, dict) else ""
    if data.get("event") == "order.status_changed" and re.fullmatch(r"ord-\d+", oid):
        ids = list(await session.scalars(select(DonateOrder.id).where(
            DonateOrder.provider_ref == oid, DonateOrder.status == "processing",
            DonateOrder.package_id.in_(select(DonatePackage.id).where(DonatePackage.provider_id == provider_id)))))
        for i in ids:
            await enqueue("fulfil_donate", i, "check")
    return {"ok": True}


uzpinhub_webhook_router = APIRouter(prefix="/uzpinhub", tags=["uzpinhub"])


@uzpinhub_webhook_router.post("/webhook/{provider_id}")
async def uzpinhub_webhook(provider_id: int, request: Request, session: SessionDep):
    """Imzo yo'q: tanadagi ma'lumotga ishonilmaydi — faqat mos buyurtma holati API'dan qayta so'raladi."""
    import re

    row = await session.get(DonateProvider, provider_id)
    if row is None or row.kind != "uzpinhub":
        raise NotFound("Provayder")
    await session.rollback()
    try:
        data = json.loads((await request.body())[:5_000])
    except ValueError:
        return {"ok": True}
    oid = str(data.get("order_id") or "") if isinstance(data, dict) else ""
    if re.fullmatch(r"[0-9a-fA-F-]{8,64}", oid):
        ids = list(await session.scalars(select(DonateOrder.id).where(
            DonateOrder.provider_ref == oid, DonateOrder.status == "processing",
            DonateOrder.package_id.in_(select(DonatePackage.id).where(DonatePackage.provider_id == provider_id)))))
        for i in ids:
            await enqueue("fulfil_donate", i, "check")
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
