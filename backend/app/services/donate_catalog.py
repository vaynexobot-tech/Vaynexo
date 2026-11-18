"""Donat katalogi: provayderlar (bir nechta API), narx hisoblash, o'yin va paketlarni API'dan sinxronlash.

- Provayder kaliti bazada SHIFRLANGAN saqlanadi (ENCRYPTION_KEY) va hech qachon qaytarilmaydi.
- API narxi USD'da; so'm narx = tannarx × dollar kursi × (1 + ustama%), 100 so'mgacha yuqoriga yaxlitlanadi.
- Yangi topilgan o'yinlar yashirin (admin yoqadi); admin ko'rsatgan o'yinlar (bosh sahifadagilar) avtomatik bog'lanadi.
"""

import hashlib
import logging
import math
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DonateGame, DonatePackage, DonateProvider
from app.security import decrypt
from app.services import app_settings

log = logging.getLogger(__name__)

_instances: dict[int, tuple[str, object]] = {}


def price_uzs(usd, rate: int, markup_percent: int) -> int:
    """USD tannarx → so'm narx (100 so'mga yuqoriga)."""
    try:
        d = Decimal(str(usd)) * Decimal(rate) * (Decimal(100) + Decimal(markup_percent)) / Decimal(100)
    except InvalidOperation:
        return 0
    return int(math.ceil(d / 100) * 100)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def game_slug(brand_slug: str) -> str:
    """Yupay brendi → bizdagi o'yin kodi. Eski kodlar (ML, MC) saqlanadi; RU variantlar alohida."""
    parts = brand_slug.split("-")
    ru = "ru" in parts[2:] or brand_slug.endswith("-ru") or "russia" in brand_slug
    if brand_slug.startswith("mobile-legends") and not ru and len(parts) <= 3:
        return "ML"
    if brand_slug.startswith("magic-chess") and not ru:
        return "MC"
    return brand_slug


# ------------------------------------------------------------------ provayder nusxalari
def build_provider(row: DonateProvider):
    key = decrypt(row.key_enc) or ""
    if row.kind == "yupay":
        from app.providers.yupay import YupayProvider

        return YupayProvider(key, row.base_url)
    from app.providers.http import HttpProvider

    return HttpProvider(row.base_url, key, cfg=row.config or {})


def provider_instance(row: DonateProvider):
    sig = hashlib.sha1(f"{row.kind}|{row.base_url}|{row.key_enc}|{row.config}".encode()).hexdigest()
    cached = _instances.get(row.id)
    if cached and cached[0] == sig:
        return cached[1]
    inst = build_provider(row)
    _instances[row.id] = (sig, inst)
    return inst


def forget_provider(pid: int) -> None:
    _instances.pop(pid, None)


async def provider_for_package(session: AsyncSession, pkg: DonatePackage):
    """Paket qaysi API orqali yetkaziladi. Bog'lanmagan bo'lsa — Render'dagi eski sozlama (yoki qo'lda)."""
    from app.providers import get_provider
    from app.providers.manual import ManualProvider

    if pkg.provider_id:
        row = await session.get(DonateProvider, pkg.provider_id)
        if row is None or not row.is_active or not row.key_enc:
            return ManualProvider()  # API o'chirilgan — admin qo'lda bajaradi
        return provider_instance(row)
    return get_provider()


async def provider_for_game(session: AsyncSession, game: DonateGame | None):
    from app.providers import get_provider
    from app.providers.manual import ManualProvider

    if game is not None and game.provider_id:
        row = await session.get(DonateProvider, game.provider_id)
        if row is None or not row.is_active or not row.key_enc:
            return ManualProvider()
        return provider_instance(row)
    return get_provider()


# ------------------------------------------------------------------ narx
async def rate_and_markup(session: AsyncSession) -> tuple[int, int]:
    return (int(await app_settings.get_value(session, "donate_usd_rate")),
            int(await app_settings.get_value(session, "donate_markup_percent")))


async def reprice(session: AsyncSession) -> int:
    """Saqlangan USD tannarxlardan so'm narxlarni qayta hisoblaydi (kurs yoki ustama o'zgarganda)."""
    rate, markup = await rate_and_markup(session)
    n = 0
    for p in await session.scalars(select(DonatePackage).where(DonatePackage.source == "api", DonatePackage.cost_usd.is_not(None))):
        new = price_uzs(p.cost_usd, rate, markup)
        if new and new != p.price:
            p.price, n = new, n + 1
    return n


# ------------------------------------------------------------------ sinxronlash
def _fields(product: dict) -> list[dict]:
    out = []
    for f in (product.get("required_fields") or [])[:2]:
        if not f.get("key"):
            continue
        out.append({"key": f["key"], "label": f.get("label") or f["key"], "placeholder": f.get("placeholder") or "",
                    "pattern": f.get("pattern") or ""})
    return out


async def sync_provider(session: AsyncSession, row: DonateProvider) -> dict:
    """Katalogni olib, o'yinlar va paketlarni yangilaydi. Faqat qat'iy nominalli (fixed) SKU'lar."""
    prov = provider_instance(row)
    brands = await prov.catalog(force=True)
    rate, markup = await rate_and_markup(session)
    games = {g.slug: g for g in await session.scalars(select(DonateGame))}
    pkgs = {(p.provider_id, p.provider_sku): p for p in await session.scalars(
        select(DonatePackage).where(DonatePackage.provider_id == row.id))}
    seen: set[str] = set()
    new_games: list[str] = []
    n_pk = 0
    for b in brands:
        bslug = str(b.get("slug") or "")
        if not bslug:
            continue
        slug = game_slug(bslug)
        g = games.get(slug)
        if g is None:  # admin oldindan qo'ygan joy-egasi (nomi bir xil) — slug'ini almashtiramiz
            ph = next((x for x in games.values() if x.provider_id is None and x.slug not in ("ML", "MC")
                       and (norm(x.name) == norm(b.get("name", "")) or norm(x.slug) == norm(bslug))
                       and not any(p.game == x.slug for p in pkgs.values())), None)
            if ph is not None:
                keep = dict(name=ph.name, featured_slot=ph.featured_slot, popular=ph.popular, sort=ph.sort, is_active=ph.is_active)
                await session.delete(ph)
                await session.flush()
                games.pop(ph.slug, None)
                g = DonateGame(slug=slug, **keep)
            else:
                g = DonateGame(slug=slug, name=b.get("name") or bslug, is_active=False, sort=500)
                new_games.append(g.name)
            session.add(g)
            games[slug] = g
        first_link = g.provider_id is None
        g.provider_id, g.brand_slug = row.id, bslug
        g.logo_url = b.get("logo_url") or g.logo_url
        g.hero_url = b.get("hero_image_url") or g.hero_url
        g.category = b.get("category_name") or g.category
        g.synced_at = datetime.now(timezone.utc)
        products = b.get("products") or []
        if products and not g.fields:
            g.fields = _fields(products[0])
        if first_link:  # qo'lda kiritilgan eski paketlar API paketlariga almashtiriladi
            for p in (await session.scalars(select(DonatePackage).where(DonatePackage.game == slug, DonatePackage.source == "manual"))):
                p.is_active = False
        i = 0
        for prod in products:
            for s in prod.get("skus") or []:
                if s.get("kind") not in (None, "fixed") or not s.get("sku_id") or s.get("price_usd") in (None, ""):
                    continue
                key = (row.id, str(s["sku_id"]))
                seen.add(f"{row.id}:{s['sku_id']}")
                price = price_uzs(s["price_usd"], rate, markup)
                if price <= 0:
                    continue
                name = str(s.get("name") or prod.get("name") or "")[:128]
                p = pkgs.get(key)
                if p is None:
                    p = DonatePackage(game=slug, name=name, price=price, provider_sku=str(s["sku_id"]), provider_id=row.id, source="api")
                    session.add(p)
                    pkgs[key] = p
                p.game, p.name, p.price, p.cost_usd = slug, name, price, str(s["price_usd"])
                p.is_active = s.get("stock") != 0 and not p.admin_off
                p.sort = i
                i += 1
                n_pk += 1
    for key, p in pkgs.items():  # katalogdan yo'qolganlar
        if p.source == "api" and f"{row.id}:{p.provider_sku}" not in seen:
            p.is_active = False
    row.synced_at = datetime.now(timezone.utc)
    row.last_ok_at, row.last_error = row.synced_at, None
    return {"games": len({game_slug(str(b.get('slug'))) for b in brands}), "packages": n_pk, "new_games": new_games}


async def sync_all() -> None:
    """Cron: faol provayderlarni sinxronlaydi (xato bitta provayderni to'xtatmaydi)."""
    from app.api.donate import invalidate_packages_cache
    from app.db import SessionLocal

    async with SessionLocal() as s:
        rows = list(await s.scalars(select(DonateProvider).where(DonateProvider.is_active.is_(True), DonateProvider.key_enc != "")))
    for row in rows:
        try:
            async with SessionLocal() as s, s.begin():
                r = await s.get(DonateProvider, row.id)
                await sync_provider(s, r)
        except Exception as e:  # noqa: BLE001
            log.warning("Katalog sinxronlanmadi (%s): %s", row.name, e)
            async with SessionLocal() as s, s.begin():
                r = await s.get(DonateProvider, row.id)
                if r:
                    r.last_error = f"{e.__class__.__name__}: {str(e)[:200]}"
    await invalidate_packages_cache()
