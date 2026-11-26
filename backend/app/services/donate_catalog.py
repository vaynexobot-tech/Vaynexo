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

from sqlalchemy import select
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


ML_BRANDS = ("mobile-legends", "mobile-legends-bang-bang", "mobile-legends-global", "mlbb")
MC_BRANDS = ("magic-chess", "magic-chess-gogo", "magic-chess-go-go", "magic-chess-gogo-global")


def game_slug(brand_slug: str) -> str:
    """Yupay brendi → bizdagi o'yin kodi. Faqat asosiy (global, to'g'ridan-to'g'ri) brendlar ML/MC ga bog'lanadi;
    mintaqa (RU, TR, ID ...) va vaucher variantlari alohida o'yin bo'lib qoladi."""
    if brand_slug in ML_BRANDS:
        return "ML"
    if brand_slug in MC_BRANDS:
        return "MC"
    return brand_slug


# ------------------------------------------------------------------ provayder nusxalari
def build_provider(row: DonateProvider):
    key = decrypt(row.key_enc) or ""
    if row.kind == "yupay":
        from app.providers.yupay import YupayProvider

        return YupayProvider(key, row.base_url)
    if row.kind == "uzpinhub":
        from app.config import settings
        from app.providers.uzpinhub import UzpinhubProvider

        return UzpinhubProvider(key, row.base_url, callback_url=f"{settings.webapp_url.rstrip('/')}/api/uzpinhub/webhook/{row.id}")
    if row.kind == "fazercards" or (row.kind == "http" and "fzr.cards" in (row.base_url or "")):  # adashib «Boshqa API» tanlangan
        from app.providers.fazercards import FazerCardsProvider

        return FazerCardsProvider(key, row.base_url)
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


_BONUS = re.compile(r"\(\s*(\d+)\s*\+\s*(\d+)\s*\)")


_PLUS = re.compile(r"^\$?\s*(\d[\d,]*)\s*\+\s*(\d[\d,]*)")
_LEAD = re.compile(r"^\$?\s*(\d[\d,]*)")


def parse_amount(name: str) -> tuple[int, int]:
    """Nom boshidagi miqdor: «172 (156+16) Diamonds» -> (156, 16); «50 + 5 Diamonds» -> (50, 5); «60 UC» -> (60, 0).
    Son nom boshida bo'lmasa (Prime (1 Month), Level Up Package 6) — maxsus paket: (0, 0)."""
    n = name.strip()
    num = lambda x: int(x.replace(",", ""))  # noqa: E731
    m = _PLUS.match(n)
    if m:
        return num(m.group(1)), num(m.group(2))
    m = _LEAD.match(n)
    if not m:
        return 0, 0
    b = _BONUS.search(n)
    if b:
        return int(b.group(1)), int(b.group(2))
    v = num(m.group(1))
    return (v, 0) if v < 10**9 else (0, 0)


def clean_name(name: str, game_name: str) -> str:
    """Paket nomidan o'yin nomini olib tashlaydi: «Mobile Legends 86 Diamonds» -> «86 Diamonds»."""
    n = name.strip()
    for prefix in (game_name, game_name.replace(":", "")):
        if prefix and n.lower().startswith(prefix.lower()) and len(n) > len(prefix) + 1:
            n = n[len(prefix):].strip(" -:·|")
    return n or name


# ------------------------------------------------------------------ sinxronlash
def _fields(product: dict) -> list[dict]:
    out = []
    for f in (product.get("required_fields") or [])[:2]:
        if not f.get("key"):
            continue
        out.append({"key": f["key"], "label": f.get("label") or f["key"], "placeholder": f.get("placeholder") or "",
                    "pattern": f.get("pattern") or ""})
    return out


def _log_samples(brands: list[dict]) -> None:
    """Diagnostika: asosiy o'yinlar brendlari tuzilmasi logga (kalitlar/sirlar yo'q — faqat katalog)."""
    import json

    want = ("mobile-legends", "magic-chess", "steam", "pubg-mobile", "roblox")
    kinds_seen: set[str] = set()
    for b in brands:
        bs = str(b.get("slug") or "")
        prods = b.get("products") or []
        sk = [x for p in prods for x in (p.get("skus") or [])]
        kinds = sorted({str(x.get("kind")) for x in sk})
        new_kind = next((k for k in kinds if k not in kinds_seen), None)
        if bs.startswith(want) or new_kind:
            kinds_seen.update(kinds)
            sample = {"slug": bs, "name": b.get("name"), "kinds": kinds, "n_skus": len(sk),
                      "products": [{k: v for k, v in p.items() if k != "skus"} | {"skus": (p.get("skus") or [])[:2]} for p in prods[:3]]}
            log.info("KATALOG_NAMUNA %s", json.dumps(sample, ensure_ascii=False)[:3000])


AMOUNT_PRESETS = (5, 10, 20, 50, 100)  # erkin summali SKU (Steam hamyon) uchun tayyor nominallar, USD
UNIT_PRESETS = (50, 100, 250, 500, 1000, 2500, 5000)  # donalab SKU (Stars va h.k.)


def _dec_or_none(v) -> Decimal | None:
    try:
        return Decimal(str(v)) if v not in (None, "") else None
    except (InvalidOperation, ValueError):
        return None


def sku_variants(s: dict, prod: dict, game_name: str) -> list[tuple[str, str, str]]:
    """SKU -> [(provider_sku, nom, tannarx_usd)]. fixed — bitta; amount/unit — tayyor nominallar.
    provider_sku: «<sku_id>» yoki «<sku_id>@amt:10» / «<sku_id>@qty:100»."""
    sid = str(s.get("sku_id") or "")
    if not sid:
        return []
    kind = s.get("kind") or "fixed"
    if kind == "fixed":
        if s.get("price_usd") in (None, ""):
            return []
        return [(sid, clean_name(str(s.get("name") or prod.get("name") or ""), game_name)[:128], str(s["price_usd"]))]
    unit = _dec_or_none(s.get("unit_price_usd"))
    if unit is None or unit <= 0:
        return []
    out = []
    if kind == "amount":
        lo, hi = _dec_or_none(s.get("min_amount_usd")) or Decimal(1), _dec_or_none(s.get("max_amount_usd")) or Decimal(500)
        for a in AMOUNT_PRESETS:
            if lo <= a <= hi:
                out.append((f"{sid}@amt:{a}", f"${a}", str((unit * a).quantize(Decimal("0.01")))))
    elif kind == "unit":
        lo, hi = s.get("min_qty") or 1, s.get("max_qty") or 10**9
        label = str(s.get("unit") or "dona")
        for q in UNIT_PRESETS:
            if lo <= q <= hi:
                out.append((f"{sid}@qty:{q}", f"{q} {label}", str((unit * q).quantize(Decimal("0.01")))))
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
    _log_samples(brands)
    for b in brands:
        bslug = str(b.get("slug") or "")
        if not bslug:
            continue
        slug = ((row.config or {}).get("map") or {}).get(bslug) or game_slug(bslug)  # admin bog'lagan: fz-mobile-legends → ML
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
                g = DonateGame(slug=slug, name=b.get("name") or bslug, is_active=False, sort=500)  # admin yoqadi
                new_games.append(g.name)
            session.add(g)
            games[slug] = g
        first_link = g.provider_id is None
        owner = g.provider_id in (None, row.id)  # o'yinda boshqa API tanlangan bo'lsa — faqat paketlar yangilanadi
        g.brands = {**(g.brands or {}), str(row.id): bslug}
        products = b.get("products") or []
        if owner:
            g.provider_id, g.brand_slug = row.id, bslug
            g.logo_url = b.get("logo_url") or g.logo_url
            g.hero_url = b.get("hero_image_url") or g.hero_url
            g.category = b.get("category_name") or g.category
            g.synced_at = datetime.now(timezone.utc)
            if products and not g.fields:
                g.fields = _fields(next((p for p in products if p.get("required_fields")), products[0]))
        game_pkgs: list[DonatePackage] = []
        all_voucher = bool(products) and all(not p.get("required_fields") for p in products)
        if all_voucher and owner:
            g.fields = []  # faqat kod beriladigan o'yin — ID so'ralmaydi
        for prod in products:
            delivery = "topup" if prod.get("required_fields") else "voucher"  # maydonsiz mahsulot — kod beriladi
            for s in prod.get("skus") or []:
                for sku, name, cost in sku_variants(s, prod, g.name):
                    key = (row.id, sku)
                    seen.add(f"{row.id}:{sku}")
                    price = price_uzs(cost, rate, markup)
                    if price <= 0:
                        continue
                    p = pkgs.get(key)
                    if p is None:
                        p = DonatePackage(game=slug, name=name, price=price, provider_sku=sku, provider_id=row.id, source="api")
                        session.add(p)
                        pkgs[key] = p
                    p.game, p.name, p.price, p.cost_usd, p.delivery = slug, name, price, cost, delivery
                    p.diamonds, p.bonus = parse_amount(name)
                    p.is_active = s.get("stock") != 0 and not p.admin_off
                    game_pkgs.append(p)
                    n_pk += 1
        # Tartib: oddiy nominallar (miqdori bor) narx bo'yicha, keyin maxsus paketlar (pass, obuna) narx bo'yicha
        game_pkgs.sort(key=lambda x: (x.diamonds == 0, x.price))
        for i, p in enumerate(game_pkgs):
            p.sort = i * 10
        if first_link and game_pkgs:
            # Qo'lda kiritilganlar qoladi (qo'shimcha); faqat API'da xuddi shu miqdordagisi borlari o'chiriladi
            api_amounts = {(p.diamonds + p.bonus) for p in game_pkgs if p.diamonds}
            for p in (await session.scalars(select(DonatePackage).where(DonatePackage.game == slug, DonatePackage.source == "manual"))):
                if p.diamonds and (p.diamonds + p.bonus) in api_amounts:
                    p.is_active = False
    for key, p in pkgs.items():  # katalogdan yo'qolganlar
        if p.source == "api" and f"{row.id}:{p.provider_sku}" not in seen:
            p.is_active = False
    row.synced_at = datetime.now(timezone.utc)
    row.last_ok_at, row.last_error = row.synced_at, None
    return {"games": len({str(b.get('slug')) for b in brands}), "packages": n_pk, "new_games": new_games}


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
            log.warning("Katalog sinxronlanmadi (%s): %r", row.name, e)
            from app.providers.base import ProviderAuthError

            async with SessionLocal() as s, s.begin():
                r = await s.get(DonateProvider, row.id)
                if r and isinstance(e, ProviderAuthError):  # xato kalit bilan qayta-qayta urinmaslik (IP bloklanishi mumkin)
                    r.is_active = False
                if r:
                    r.last_error = f"{e.__class__.__name__}: {(str(e) or repr(e))[:200]}"
    await invalidate_packages_cache()
