"""Telegram Premium va Stars buyurtmalarini Yupay orqali avtomatik bajarish.

Gift va NFT — qo'lda (admin). Mos paket topilmasa, provayder yoqilmagan bo'lsa yoki ketma-ket xato bo'lsa —
buyurtma `processing` holatida qoladi va admin «Bajarildi / Qaytarish» ni bosadi (pul hech qachon yo'qolmaydi).
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import DonateGame, DonatePackage, DonateProvider, TgOrder
from app.services import app_settings
from app.services.notify import Outbox, fmt, webapp_button

log = logging.getLogger(__name__)

AUTO_KINDS = {"premium": "telegram-premium", "stars": "telegram-stars"}
MAX_CREATE_ATTEMPTS = 3
MAX_STATUS_CHECKS = 40
RETRY_DELAY = 20
CHECK_DELAY = 30


def order_ref(order_id: int) -> str:
    return f"VX-T{order_id}"


async def enabled(session: AsyncSession) -> bool:
    return await app_settings.get_value(session, "tg_auto") == "on"


async def find_target(session: AsyncSession, kind: str, details: dict) -> tuple[DonatePackage, DonateProvider, str] | None:
    """(paket, provayder, provayder SKU) — yoki None (qo'lda bajariladi)."""
    slug = AUTO_KINDS.get(kind)
    if not slug:
        return None
    game = await session.get(DonateGame, slug)
    if game is None or game.provider_id is None:
        return None
    prov = await session.get(DonateProvider, game.provider_id)
    if prov is None or not prov.is_active or not prov.key_enc:
        return None
    pkgs = list(await session.scalars(select(DonatePackage).where(
        DonatePackage.game == slug, DonatePackage.is_active.is_(True), DonatePackage.provider_id == prov.id).order_by(DonatePackage.sort)))
    if kind == "premium":
        p = next((x for x in pkgs if x.diamonds == int(details.get("months") or 0)), None)
        return (p, prov, p.provider_sku) if p else None
    p = next((x for x in pkgs if "@qty:" in x.provider_sku), None)  # Stars: «<sku_id>@qty:N» — miqdorni o'zimiz qo'yamiz
    if p is None:
        return None
    qty = int(details.get("stars") or 0)  # bonus — bizning sovg'amiz, Yupay'dan faqat sotib olingan miqdor so'raladi
    return (p, prov, f"{p.provider_sku.split('@')[0]}@qty:{qty}") if qty > 0 else None


async def yupay_costs(session: AsyncSession) -> dict | None:
    """Yupay tannarxi so'mda: {"premium": {oy: so'm}, "star": 1 Star so'm (kasr)} — yoki None (Yupay ulanmagan)."""
    from decimal import Decimal, InvalidOperation

    if not await enabled(session):
        return None
    rate = int(await app_settings.get_value(session, "donate_usd_rate"))
    out: dict = {"premium": {}, "star": None}
    for kind, slug in AUTO_KINDS.items():
        game = await session.get(DonateGame, slug)
        if game is None or game.provider_id is None:
            continue
        pkgs = list(await session.scalars(select(DonatePackage).where(
            DonatePackage.game == slug, DonatePackage.provider_id == game.provider_id, DonatePackage.is_active.is_(True))))
        try:
            if kind == "premium":
                for p in pkgs:
                    if p.diamonds and p.cost_usd:
                        out["premium"][p.diamonds] = float(Decimal(p.cost_usd) * rate)
            else:  # eng katta paket — yaxlitlash xatosi eng kichik
                big = max((p for p in pkgs if p.diamonds and p.cost_usd), key=lambda p: p.diamonds, default=None)
                if big:
                    out["star"] = float(Decimal(big.cost_usd) / big.diamonds * rate)
        except (InvalidOperation, ValueError):
            continue
    return out if (out["premium"] or out["star"]) else None


async def eligible(session: AsyncSession, kind: str, details: dict) -> bool:
    return await enabled(session) and await find_target(session, kind, details) is not None


async def _stars_in_range(provider, sku: str) -> bool:
    """Yupay min/max doirasi (katalogdan). Doiradan tashqarida bo'lsa — qo'lda bajariladi."""
    base, _, opt = sku.partition("@")
    try:
        qty = int(opt.split(":")[1])
        for b in await provider.catalog():
            for p in b.get("products") or []:
                for s in p.get("skus") or []:
                    if str(s.get("sku_id")) == base:
                        lo, hi = s.get("min_qty") or 1, s.get("max_qty") or 10**9
                        return lo <= qty <= hi
    except Exception:  # noqa: BLE001
        return True  # tekshirib bo'lmasa — Yupay o'zi rad etadi
    return True


async def fulfil_step(sessions: async_sessionmaker, order_id: int, mode: str, out: Outbox) -> tuple[str, int] | None:
    """Bitta qadam. Keyingi qadam kerak bo'lsa (mode, kechikish_sekund) qaytaradi."""
    from app.services import donate_catalog
    from app.services.services import resolve_tg_order

    async with sessions() as session, session.begin():
        order = await session.scalar(select(TgOrder).where(TgOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
        if order is None or order.status != "processing" or order.kind not in AUTO_KINDS:
            return None
        auto = dict(order.details.get("auto") or {})
        if auto.get("manual"):
            return None
        target = await find_target(session, order.kind, order.details)
        if target is None or not await enabled(session):
            return None  # qo'lda
        pkg, prov_row, sku = target
        auto["attempts"] = attempts = int(auto.get("attempts", 0)) + 1
        order.details = {**order.details, "auto": auto}
        provider = donate_catalog.provider_instance(prov_row)
        username = order.target_username

    if order.kind == "stars" and not await _stars_in_range(provider, sku):
        return await _to_manual(sessions, order_id, "Stars miqdori API chegarasidan tashqarida", out)

    ref = order_ref(order_id)
    if mode == "create" and attempts > 1:
        prev = await provider.status(ref)  # oldingi so'rov aslida yetgan bo'lishi mumkin
        result = prev if prev.status in ("success", "pending") else await provider.create(ref, sku, "telegram", username, "")
    elif mode == "create":
        result = await provider.create(ref, sku, "telegram", username, "")
    else:
        result = await provider.status(ref)

    if result.status == "success":
        async with sessions() as session, session.begin():
            await resolve_tg_order(session, order_id, "done", "avtomatik", out)
        return None
    if result.status == "failed":
        async with sessions() as session, session.begin():
            await resolve_tg_order(session, order_id, "refund", "Avtomatik bajarib bo'lmadi. Username to'g'riligini tekshirib, qayta urinib ko'ring", out)
        out.admins(f"❗️TG buyurtma #{order_id} avtomatik bajarilmadi, pul qaytarildi.\nSabab (API): {result.message}", topic="tg")
        return None
    if result.status == "pending":
        if attempts >= MAX_STATUS_CHECKS:
            return await _to_manual(sessions, order_id, "API juda uzoq bajaryapti", out)
        return ("check", CHECK_DELAY)
    # unknown
    if mode == "create" and attempts < MAX_CREATE_ATTEMPTS:
        return ("create", RETRY_DELAY * attempts)
    if mode == "check" and attempts < MAX_STATUS_CHECKS:
        return ("check", CHECK_DELAY)
    return await _to_manual(sessions, order_id, f"API javob bermadi: {result.message}", out)


async def _to_manual(sessions: async_sessionmaker, order_id: int, why: str, out: Outbox) -> None:
    async with sessions() as session, session.begin():
        order = await session.scalar(select(TgOrder).where(TgOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
        if order is None or order.status != "processing":
            return None
        order.details = {**order.details, "auto": {**(order.details.get("auto") or {}), "manual": True, "why": why[:200]}}
        out.admins(f"⚠️ TG buyurtma #{order_id} qo'lda bajarilsin: {order.title} → {order.target_username}\n"
                   f"Sabab: {why}\nSumma: {fmt(order.price)}", webapp_button("Bajarish", "/admin"), topic="tg")
    return None
