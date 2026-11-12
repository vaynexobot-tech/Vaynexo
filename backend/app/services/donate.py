"""Almaz donat: pul yechiladi -> provayder API -> natija.

* Provayder aniq rad etsa (failed) — pul darhol hamyonga qaytadi, foydalanuvchi va admin xabardor qilinadi.
* Javob kelmasa (timeout/5xx — `unknown`) — almaz tushgan bo'lishi mumkin, shuning uchun avval holat
  so'raladi va bir necha marta qayta uriniladi. Shunda ham noma'lum qolsa, buyurtma `review` holatiga
  o'tadi va admin qaror qiladi (aks holda ham almaz, ham pul berib yuborilishi mumkin).
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError, BadState, NotFound
from app.models import DonateOrder, DonatePackage
from app.providers import get_provider
from app.services import wallet
from app.services.notify import Outbox, fmt, webapp_button

MAX_CREATE_ATTEMPTS = 3
MAX_STATUS_CHECKS = 40
RETRY_DELAY = 20  # sekund
CHECK_DELAY = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_id(value: str, max_len: int) -> str:
    value = (value or "").strip()
    if not value.isdigit() or len(value) > max_len:
        raise AppError("bad_player_id", "ID faqat raqamlardan iborat bo'lishi kerak")
    return value


async def create_order(session: AsyncSession, user_id: int, package_id: int, player_id: str, zone_id: str) -> DonateOrder:
    pkg = await session.get(DonatePackage, package_id)
    if pkg is None or not pkg.is_active:
        raise NotFound("Paket")
    player_id = _clean_id(player_id, 20)
    zone_id = _clean_id(zone_id, 10) if pkg.game == "ML" else (zone_id or "").strip()[:10]
    order = DonateOrder(
        user_id=user_id,
        package_id=pkg.id,
        game=pkg.game,
        title=pkg.name,
        player_id=player_id,
        zone_id=zone_id,
        price=pkg.price,
        status="processing",
    )
    session.add(order)
    await session.flush()
    await wallet.debit(session, user_id, pkg.price, "donate", f"donate:{order.id}", ref_type="donate", ref_id=order.id)
    return order


def order_ref(order: DonateOrder) -> str:
    return f"VX-D{order.id}"


async def _finish_success(session: AsyncSession, order: DonateOrder, ref: str | None, out: Outbox) -> None:
    order.status = "done"
    order.provider_ref = ref or order.provider_ref
    order.finished_at = _now()
    order.error = None
    await wallet.add_ticket(session, order.user_id)
    out.user(
        order.user_id,
        f"💎 {order.title} yetkazildi!\nID: {order.player_id}"
        + (f" ({order.zone_id})" if order.zone_id else "")
        + f"\nBuyurtma: {order_ref(order)}",
        webapp_button("Xaridlar tarixi", "/history"),
    )


async def refund(session: AsyncSession, order: DonateOrder, reason: str, out: Outbox, notify_admin: bool = True) -> None:
    order.status = "refunded"
    order.error = reason[:500]
    order.finished_at = _now()
    await wallet.credit(
        session, order.user_id, order.price, "donate_refund", f"donate_refund:{order.id}", ref_type="donate", ref_id=order.id
    )
    out.user(
        order.user_id,
        f"↩️ {order.title} yetkazib bo'lmadi. {fmt(order.price)} hamyoningizga qaytarildi.\nBuyurtma: {order_ref(order)}",
        webapp_button("Hamyon", "/wallet"),
    )
    if notify_admin:
        out.admins(f"❗️Donat xatosi, pul qaytarildi.\n{order_ref(order)} · {order.title}\nID {order.player_id} ({order.zone_id})\nSabab: {reason}", topic="buyurtma")


async def fulfil_step(sessions: async_sessionmaker, order_id: int, mode: str, out: Outbox) -> tuple[str, int] | None:
    """Bitta qadam. Keyingi qadam kerak bo'lsa (mode, kechikish_sekund) qaytaradi.

    mode: "create" — buyurtma berish; "check" — holatni so'rash.
    """
    provider = get_provider()
    async with sessions() as session, session.begin():
        order = await session.scalar(select(DonateOrder).where(DonateOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
        if order is None or order.status != "processing":
            return None
        order.attempts += 1
        attempts = order.attempts
        ref = order_ref(order)
        sku, game, pid, zid = order.package.provider_sku, order.game, order.player_id, order.zone_id

    if mode == "create" and attempts > 1:
        # Qayta urinishdan oldin: balki oldingi so'rov aslida yetib borgandir.
        prev = await provider.status(ref)
        result = prev if prev.status in ("success", "pending") else await provider.create(ref, sku, game, pid, zid)
    elif mode == "create":
        result = await provider.create(ref, sku, game, pid, zid)
    else:
        result = await provider.status(ref)

    async with sessions() as session, session.begin():
        order = await session.scalar(select(DonateOrder).where(DonateOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
        if order is None or order.status != "processing":
            return None
        if result.ref:
            order.provider_ref = result.ref
        if result.status == "success":
            await _finish_success(session, order, result.ref, out)
            return None
        if result.status == "failed":
            await refund(session, order, result.message or "provayder rad etdi", out)
            return None
        if result.status == "manual":
            order.status = "review"
            out.admins(
                f"💎 Donat buyurtma {ref}\n{order.title}\nO'yin: {order.game} · ID {pid}" + (f" ({zid})" if zid else "")
                + f"\nSumma: {fmt(order.price)}\n\nAlmazni tashlang va natijani bosing:",
                {"inline_keyboard": [[{"text": "✅ Bajarildi", "callback_data": f"donate:done:{order.id}"},
                                      {"text": "↩️ Pulni qaytarish", "callback_data": f"donate:refund:{order.id}"}]]},
                topic="buyurtma",
            )
            out.user(order.user_id, f"⏳ {order.title} buyurtmangiz qabul qilindi. Odatda 5–30 daqiqada tushadi.")
            return None
        if result.status == "pending":
            if attempts >= MAX_STATUS_CHECKS:
                order.status = "review"
                out.admins(f"⏳ Donat juda uzoq kutilmoqda, tekshiring: {ref} · {order.title}", webapp_button("Admin panel", "/admin"), topic="buyurtma")
                return None
            return ("check", CHECK_DELAY)
        # unknown
        order.error = result.message[:500]
        if mode == "create" and attempts < MAX_CREATE_ATTEMPTS:
            return ("create", RETRY_DELAY * attempts)
        if mode == "check" and attempts < MAX_STATUS_CHECKS:
            return ("check", CHECK_DELAY)
        order.status = "review"
        out.admins(
            f"⚠️ Donat holati noma'lum (provayder javob bermadi): {ref} · {order.title}\n"
            f"ID {pid} ({zid}). Provayder kabinetida tekshirib, admin paneldan «Bajarildi» yoki «Pulni qaytarish» ni bosing.",
            webapp_button("Admin panel", "/admin"), topic="buyurtma",
        )
        out.user(order.user_id, f"⏳ {order.title} buyurtmangiz tekshirilmoqda. Natija tez orada xabar qilinadi.")
        return None


async def admin_resolve(session: AsyncSession, order_id: int, action: str, out: Outbox) -> DonateOrder:
    order = await session.scalar(select(DonateOrder).where(DonateOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if order is None:
        raise NotFound("Buyurtma")
    if order.status not in ("review", "processing"):
        raise BadState("Buyurtma allaqachon yakunlangan")
    if action == "done":
        await _finish_success(session, order, None, out)
    elif action == "refund":
        await refund(session, order, "admin qaytardi", out, notify_admin=False)
    else:
        raise AppError("bad_action", "Noma'lum amal")
    return order
