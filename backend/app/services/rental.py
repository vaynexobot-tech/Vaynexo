"""Account ijara.

* Egasi akkauntni soatbay narx bilan qo'yadi, kirish ma'lumotlarini oldindan beradi (shifrlanadi). Admin tasdiqlaydi.
* Ijarachi muddatni tanlaydi (12 soat, 24 soat, 3 kun, 1 hafta), ijara narxi + depozit balansidan yechiladi va garantda turadi.
  Login/parol to'lovdan keyin darhol ochiladi.
* Muddat tugagach (ended) egasi parolni almashtirib, "Akkaunt qaytdi" ni bosadi: egasiga ijara narxi (komissiyasiz),
  ijarachiga depozit qaytadi. Egasi REVIEW_HOURS ichida javob bermasa, bitim avtomatik yakunlanadi.
* Muammo bo'lsa egasi (akkauntga zarar) yoki ijarachi (akkaunt ishlamadi) nizo ochadi, admin hal qiladi.
* Ijaraga olish uchun kamida bir marta hamyonni haqiqiy pul bilan to'ldirgan bo'lish kerak (soxta akkauntlarga qarshi).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, BadState, Forbidden, NotFound
from app.models import Rental, RentListing, Topup
from app.security import decrypt, encrypt
from app.services import app_settings, wallet
from app.services.notify import Outbox, fmt, webapp_button

DURATIONS = {12: "12 soat", 24: "24 soat", 72: "3 kun", 168: "1 hafta"}
REVIEW_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lock(model, oid):
    return select(model).where(model.id == oid).with_for_update().execution_options(populate_existing=True)


async def config(session: AsyncSession) -> dict:
    s = await app_settings.get_many(session, "rent_deposit_type", "rent_deposit_percent", "rent_deposit_fixed", "rent_commission_percent",
                                    "rent_discount_24", "rent_discount_72", "rent_discount_168")
    disc = {12: 0, 24: s["rent_discount_24"], 72: s["rent_discount_72"], 168: s["rent_discount_168"]}
    return {"durations": [{"hours": h, "label": lbl, "discount": int(disc.get(h, 0))} for h, lbl in DURATIONS.items()], **s}


def price_for(price_per_hour: int, hours: int, cfg: dict) -> int:
    """Narx = soatlik narx × soat − muddat chegirmasi (%)."""
    disc = next((d["discount"] for d in cfg["durations"] if d["hours"] == hours), 0)
    gross = price_per_hour * hours
    return gross - gross * int(disc) // 100


def deposit_for(price: int, cfg: dict) -> int:
    if cfg["rent_deposit_type"] == "fixed":
        return int(cfg["rent_deposit_fixed"])
    return price * int(cfg["rent_deposit_percent"]) // 100


def validate_listing(data: dict, need_creds: bool) -> dict:
    from app.services.market import validate_listing_data

    base = validate_listing_data({**data, "price": max(1_000, int(data.get("price_per_hour") or 0))})
    pph = int(data.get("price_per_hour") or 0)
    if not 500 <= pph <= 10_000_000:
        raise AppError("bad_price", "Soatlik narx 500 so'mdan kam bo'lmasin")
    out = {k: base[k] for k in ("game", "title", "rank", "server", "collection_level", "skins", "heroes", "description", "media")}
    out["price_per_hour"] = pph
    creds = (data.get("credentials") or "").strip()
    if need_creds or creds:
        if not 3 <= len(creds) <= 2000:
            raise AppError("bad_credentials", "Akkauntga kirish ma'lumotlarini kiriting (faqat ijarachiga, ijara vaqtida ko'rinadi)")
        out["credentials_enc"] = encrypt(creds)
    return out


async def create_listing(session: AsyncSession, owner_id: int, data: dict, out: Outbox) -> RentListing:
    from app.services.account import require_kyc

    await require_kyc(session, owner_id, "rental")
    item = RentListing(owner_id=owner_id, status="moderation", **validate_listing(data, need_creds=True))
    session.add(item)
    await session.flush()
    out.admins(f"🔑 Yangi ijara e'loni moderatsiyada: #{item.id} · {item.title} · {fmt(item.price_per_hour)}/soat",
               webapp_button("Ko'rib chiqish", "/admin"))
    return item


async def update_listing(session: AsyncSession, owner_id: int, lid: int, data: dict) -> RentListing:
    item = await session.scalar(_lock(RentListing, lid))
    if item is None or item.owner_id != owner_id:
        raise NotFound("E'lon")
    if item.busy_until and item.busy_until > _now():
        raise BadState("Ijara davomida tahrirlab bo'lmaydi")
    for k, v in validate_listing(data, need_creds=False).items():
        setattr(item, k, v)
    item.status, item.reject_reason = "moderation", None
    return item


async def close_listing(session: AsyncSession, owner_id: int, lid: int) -> RentListing:
    item = await session.scalar(_lock(RentListing, lid))
    if item is None or item.owner_id != owner_id:
        raise NotFound("E'lon")
    item.status = "closed"
    return item


async def moderate(session: AsyncSession, lid: int, approve: bool, reason: str | None, out: Outbox) -> RentListing:
    item = await session.scalar(_lock(RentListing, lid))
    if item is None or item.status != "moderation":
        raise BadState("E'lon moderatsiyada emas")
    item.status = "active" if approve else "rejected"
    item.reject_reason = None if approve else (reason or "Qoidalarga mos emas")[:300]
    out.user(item.owner_id, f"{'✅ Ijara e`loni tasdiqlandi' if approve else '❌ Ijara e`loni rad etildi'}: {item.title}"
             + ("" if approve else f"\nSabab: {item.reject_reason}"))
    return item


async def rent(session: AsyncSession, lid: int, renter_id: int, hours: int, out: Outbox) -> Rental:
    if hours not in DURATIONS:
        raise AppError("bad_hours", "Muddatni tanlang")
    item = await session.scalar(_lock(RentListing, lid))
    if item is None or item.status != "active":
        raise NotFound("E'lon")
    if item.owner_id == renter_id:
        raise AppError("own_listing", "O'z akkauntingizni ijaraga ololmaysiz")
    if item.busy_until and item.busy_until > _now():
        raise BadState("Akkaunt hozir band")
    paid = await session.scalar(select(func.count()).select_from(Topup).where(Topup.user_id == renter_id, Topup.status == "paid"))
    if not paid:
        raise Forbidden("Ijaraga olish uchun avval hamyoningizni kamida bir marta to'ldiring")
    from app.services.account import require_kyc

    await require_kyc(session, renter_id, "rental")
    cfg = await config(session)
    price = price_for(item.price_per_hour, hours, cfg)
    deposit = deposit_for(price, cfg)
    commission = price * int(cfg["rent_commission_percent"]) // 100
    r = Rental(listing_id=item.id, renter_id=renter_id, owner_id=item.owner_id, hours=hours, price=price, deposit=deposit,
               commission=commission, status="active", starts_at=_now(), ends_at=_now() + timedelta(hours=hours), listing=item)
    session.add(r)
    await session.flush()
    await wallet.debit(session, renter_id, price + deposit, "rent_pay", f"rent:{r.id}:pay", ref_type="rental", ref_id=r.id,
                       note=f"Ijara {DURATIONS[hours]} + depozit {fmt(deposit)}")
    item.busy_until = r.ends_at
    out.user(item.owner_id, f"🔑 Akkauntingiz ijaraga olindi: {item.title} · {DURATIONS[hours]}\n"
             f"Pul garantda: {fmt(price)}. Muddat tugagach parolni almashtirib, «Akkaunt qaytdi» ni bosing.",
             webapp_button("Ijarani ochish", f"/rental/{r.id}"))
    return r


def credentials_for(r: Rental, user_id: int, is_admin: bool = False) -> str | None:
    if is_admin or (user_id == r.renter_id and r.status == "active"):
        return decrypt(r.listing.credentials_enc)
    return None


async def _payout(session: AsyncSession, r: Rental, owner_gets_deposit: int, out: Outbox, note: str) -> None:
    """Egasiga ijara narxi (komissiyasiz) + depozitning bir qismi, ijarachiga depozitning qolgani."""
    r.status, r.finished_at, r.review_until = "completed", _now(), None
    owner_amount = r.price - r.commission + owner_gets_deposit
    if owner_amount > 0:
        await wallet.credit(session, r.owner_id, owner_amount, "rent_payout", f"rent:{r.id}:payout", ref_type="rental", ref_id=r.id)
    back = r.deposit - owner_gets_deposit
    if back > 0:
        await wallet.credit(session, r.renter_id, back, "rent_deposit_back", f"rent:{r.id}:deposit", ref_type="rental", ref_id=r.id)
    item = await session.scalar(_lock(RentListing, r.listing_id))
    item.busy_until = None  # ijara yakunlandi — akkaunt yana bo'sh
    out.user(r.owner_id, f"✅ Ijara yakunlandi ({note}): +{fmt(owner_amount)}")
    out.user(r.renter_id, f"✅ Ijara yakunlandi ({note})." + (f" Depozit qaytarildi: +{fmt(back)}" if back > 0 else " Depozit ushlab qolindi."))


async def owner_confirm(session: AsyncSession, rid: int, owner_id: int, out: Outbox) -> Rental:
    r = await session.scalar(_lock(Rental, rid))
    if r is None or r.owner_id != owner_id:
        raise NotFound("Ijara")
    if r.status not in ("active", "ended"):
        raise BadState()
    if r.status == "active" and r.ends_at > _now():
        raise BadState("Ijara muddati hali tugamagan")
    await _payout(session, r, 0, out, "egasi tasdiqladi")
    return r


async def open_dispute(session: AsyncSession, rid: int, user_id: int, reason: str, out: Outbox) -> Rental:
    r = await session.scalar(_lock(Rental, rid))
    if r is None or user_id not in (r.owner_id, r.renter_id):
        raise NotFound("Ijara")
    if r.status not in ("active", "ended"):
        raise BadState()
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise AppError("bad_reason", "Muammoni batafsil yozing")
    r.status, r.review_until = "disputed", None
    r.dispute_by = "owner" if user_id == r.owner_id else "renter"
    r.dispute_reason = reason[:2000]
    out.admins(f"⚖️ Ijara nizosi #{r.id} ({r.dispute_by}): {reason[:300]}", webapp_button("Admin panel", "/admin"))
    out.user(r.renter_id if user_id == r.owner_id else r.owner_id, f"⚖️ Ijara #{r.id} bo'yicha nizo ochildi. Admin ko'rib chiqadi.")
    return r


async def resolve(session: AsyncSession, rid: int, decision: str, note: str, out: Outbox) -> Rental:
    """decision: owner — egasi haq (depozit egasiga); renter — ijarachi haq (depozit qaytadi, ijara puli to'liq qaytadi
    agar ijarachi nizo ochgan bo'lsa); normal — oddiy yakun."""
    r = await session.scalar(_lock(Rental, rid))
    if r is None or r.status != "disputed":
        raise BadState("Nizo yo'q")
    r.resolution = (note or "")[:300]
    if decision == "owner":
        await _payout(session, r, r.deposit, out, "admin qarori: egasi haq")
    elif decision == "normal":
        await _payout(session, r, 0, out, "admin qarori")
    elif decision == "renter":
        r.status, r.finished_at = "refunded", _now()
        await wallet.credit(session, r.renter_id, r.price + r.deposit, "rent_refund", f"rent:{r.id}:refund", ref_type="rental", ref_id=r.id)
        item = await session.scalar(_lock(RentListing, r.listing_id))
        item.busy_until = None
        out.user(r.renter_id, f"↩️ Ijara #{r.id}: {fmt(r.price + r.deposit)} qaytarildi (admin qarori)")
        out.user(r.owner_id, f"↩️ Ijara #{r.id} bekor qilindi (admin qarori)")
    else:
        raise AppError("bad_action", "decision: owner | renter | normal")
    return r


async def tick(session: AsyncSession, out: Outbox) -> None:
    """Cron: muddati tugaganlarni 'ended' qiladi, egasi javob bermaganlarni avtomatik yakunlaydi."""
    for rid in list(await session.scalars(select(Rental.id).where(Rental.status == "active", Rental.ends_at <= _now()).limit(100))):
        r = await session.scalar(_lock(Rental, rid))
        if r.status == "active":
            r.status, r.review_until = "ended", _now() + timedelta(hours=REVIEW_HOURS)
            out.user(r.renter_id, f"⏰ Ijara muddati tugadi: {r.listing.title}. Akkauntdan chiqing, rahmat!")
            out.user(r.owner_id, f"⏰ Ijara tugadi: {r.listing.title}. Parolni almashtiring va {REVIEW_HOURS} soat ichida "
                     "«Akkaunt qaytdi» yoki «Muammo bor» ni bosing.", webapp_button("Ijarani ochish", f"/rental/{r.id}"))
    for rid in list(await session.scalars(select(Rental.id).where(Rental.status == "ended", Rental.review_until <= _now()).limit(100))):
        r = await session.scalar(_lock(Rental, rid))
        if r.status == "ended":
            await _payout(session, r, 0, out, "avtomatik")
