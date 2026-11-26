"""Admin: premium bo'limlarni boshqarish (do'konlar, Plus, jamg'arma, striminerlar, Pro auksionlar, birga to'lov, Draft Jang)
va identifikatsiya (KYC) to'liq ro'yxati.

Har bo'lim: ro'yxat + kerakli amallar (o'chirish/yoqish, bekor qilish va pulni qaytarish, muddat qo'shish).
Pul bilan bog'liq har amal hamyon orqali (idempotent); har admin so'rovi jurnalga avtomatik yoziladi (deps → audit).
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.deps import AdminUser, SessionDep
from app.errors import AppError, BadState, NotFound
from app.models import (
    DraftDuel, PlusSub, ProProfile, ProSlot, Saving, Shop, ShopSale, Split, SplitPart, StreamDonation, Streamer, User,
)
from app.services import savings, split
from app.services.notify import Outbox

router = APIRouter(prefix="/admin/premium", tags=["admin"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d) -> str | None:
    return d.isoformat() if d else None


async def _names(session, ids) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = await session.scalars(select(User).where(User.id.in_(ids)))
    return {u.id: (f"@{u.username}" if u.username else (u.first_name or str(u.id))) for u in rows}


# ================================================================ umumiy ko'rinish
@router.get("/summary")
async def summary(admin: AdminUser, session: SessionDep):
    c = lambda q: session.scalar(q)  # noqa: E731
    now = _now()
    return {
        "shops": int(await c(select(func.count()).select_from(Shop)) or 0),
        "shop_sales": int(await c(select(func.coalesce(func.sum(ShopSale.amount), 0))) or 0),
        "shop_commission": int(await c(select(func.coalesce(func.sum(ShopSale.commission), 0))) or 0),
        "plus_active": int(await c(select(func.count()).select_from(PlusSub).where(PlusSub.until > now)) or 0),
        "savings_active": int(await c(select(func.count()).select_from(Saving).where(Saving.status == "active")) or 0),
        "savings_locked": int(await c(select(func.coalesce(func.sum(Saving.saved), 0)).where(Saving.status == "active")) or 0),
        "streamers": int(await c(select(func.count()).select_from(Streamer)) or 0),
        "stream_money": int(await c(select(func.coalesce(func.sum(StreamDonation.amount), 0)).where(StreamDonation.kind == "money")) or 0),
        "pro_pending": int(await c(select(func.count()).select_from(ProProfile).where(ProProfile.status == "pending")) or 0),
        "pro_open": int(await c(select(func.count()).select_from(ProSlot).where(ProSlot.status.in_(("open", "sold", "disputed")))) or 0),
        "pro_disputes": int(await c(select(func.count()).select_from(ProSlot).where(ProSlot.status == "disputed")) or 0),
        "splits_open": int(await c(select(func.count()).select_from(Split).where(Split.status == "open")) or 0),
        "splits_locked": int(await c(select(func.coalesce(func.sum(Split.collected), 0)).where(Split.status == "open")) or 0),
        "duels": int(await c(select(func.count()).select_from(DraftDuel)) or 0),
        "kyc_pending": int(await c(select(func.count()).select_from(User).where(User.kyc_status == "pending")) or 0),
    }


# ================================================================ do'konlar
@router.get("/shops")
async def shops_list(admin: AdminUser, session: SessionDep, q: str = ""):
    sums = (select(ShopSale.shop_id, func.coalesce(func.sum(ShopSale.amount), 0).label("s"), func.coalesce(func.sum(ShopSale.commission), 0).label("c"),
                   func.count().label("n")).group_by(ShopSale.shop_id).subquery())
    stmt = select(Shop, sums.c.s, sums.c.c, sums.c.n).outerjoin(sums, sums.c.shop_id == Shop.id).order_by(func.coalesce(sums.c.s, 0).desc(), Shop.id.desc())
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Shop.name).like(like), Shop.slug.like(like)))
    rows = (await session.execute(stmt.limit(200))).all()
    names = await _names(session, [r[0].owner_id for r in rows])
    customers = dict((await session.execute(select(User.shop_id, func.count()).where(User.shop_id.is_not(None)).group_by(User.shop_id))).all())
    return [{"id": s.id, "name": s.name, "slug": s.slug, "tagline": s.tagline, "active": s.active, "owner_id": s.owner_id, "owner": names.get(s.owner_id),
             "sales": int(sm or 0), "commission": int(cm or 0), "orders": int(n or 0), "customers": int(customers.get(s.id, 0)), "created_at": _iso(s.created_at)}
            for s, sm, cm, n in rows]


class ShopEditIn(BaseModel):
    active: bool | None = None
    name: str | None = Field(None, max_length=48)
    tagline: str | None = Field(None, max_length=120)


@router.put("/shops/{shop_id}")
async def shop_edit(shop_id: int, body: ShopEditIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        s = await session.get(Shop, shop_id, with_for_update=True)
        if s is None:
            raise NotFound("Do'kon")
        if body.name is not None:
            if len(body.name.strip()) < 2:
                raise AppError("bad_name", "Nom juda qisqa")
            s.name = body.name.strip()
        if body.tagline is not None:
            s.tagline = body.tagline.strip()
        if body.active is not None and body.active != s.active:
            s.active = body.active
            out.user(s.owner_id, "✅ Do'koningiz qayta yoqildi." if s.active else "⛔️ Do'koningiz admin tomonidan vaqtincha to'xtatildi. Savol bo'lsa — support.")
    await out.flush()
    return {"ok": True}


# ================================================================ VAYNEXO Plus
@router.get("/plus")
async def plus_list(admin: AdminUser, session: SessionDep, active: int = 1):
    stmt = select(PlusSub).order_by(PlusSub.until.desc()).limit(300)
    if active:
        stmt = stmt.where(PlusSub.until > _now())
    rows = list(await session.scalars(stmt))
    names = await _names(session, [r.user_id for r in rows])
    return [{"user_id": r.user_id, "user": names.get(r.user_id), "until": _iso(r.until), "active": r.until > _now(), "months": r.months,
             "auto_renew": r.auto_renew, "cashback_total": r.cashback_total, "auto_package_id": r.auto_package_id} for r in rows]


class PlusDaysIn(BaseModel):
    days: int = Field(ge=-365, le=365)


@router.post("/plus/{user_id}/days")
async def plus_days(user_id: int, body: PlusDaysIn, admin: AdminUser, session: SessionDep):
    """Obunaga kun qo'shish (sovg'a) yoki ayirish. Obuna yo'q bo'lsa — yaratiladi."""
    out = Outbox()
    async with session.begin():
        if await session.get(User, user_id) is None:
            raise NotFound("Foydalanuvchi")
        sub = await session.get(PlusSub, user_id, with_for_update=True)
        if sub is None:
            sub = PlusSub(user_id=user_id, until=_now(), months=0, auto_renew=False, cashback_total=0, notice="")
            session.add(sub)
        sub.until = max(sub.until, _now()) + timedelta(days=body.days) if body.days > 0 else sub.until + timedelta(days=body.days)
        sub.notice = ""
        if body.days > 0:
            out.user(user_id, f"🎁 Sizga VAYNEXO Plus'ga {body.days} kun qo'shildi!")
    await out.flush()
    return {"ok": True, "until": _iso(sub.until)}


# ================================================================ Skin jamg'armasi
@router.get("/savings")
async def savings_list(admin: AdminUser, session: SessionDep, status: str = "active"):
    stmt = select(Saving).order_by(Saving.id.desc()).limit(300)
    if status != "all":
        stmt = stmt.where(Saving.status == status)
    rows = list(await session.scalars(stmt))
    names = await _names(session, [r.user_id for r in rows])
    return [{"id": r.id, "user_id": r.user_id, "user": names.get(r.user_id), "title": r.title, "target": r.target, "saved": r.saved, "weekly": r.weekly,
             "status": r.status, "buy_at": _iso(r.buy_at), "created_at": _iso(r.created_at)} for r in rows]


@router.post("/savings/{sid}/cancel")
async def savings_cancel(sid: int, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        s = await session.get(Saving, sid)
        if s is None:
            raise NotFound("Jamg'arma")
        await savings.cancel(session, s.user_id, sid)
        out.user(s.user_id, f"↩️ «{s.title}» jamg'armasi admin tomonidan yopildi, {s.saved:,} so'm hamyoningizga qaytarildi.".replace(",", " "))
    await out.flush()
    return {"ok": True}


# ================================================================ striminerlar
@router.get("/streamers")
async def streamers_list(admin: AdminUser, session: SessionDep):
    rows = list(await session.scalars(select(Streamer).order_by(Streamer.total_count.desc(), Streamer.id.desc()).limit(300)))
    names = await _names(session, [r.user_id for r in rows])
    return [{"id": r.id, "user_id": r.user_id, "user": names.get(r.user_id), "name": r.name, "slug": r.slug, "active": r.active,
             "count": r.total_count, "packs": r.total_packs, "money": r.total_money, "created_at": _iso(r.created_at)} for r in rows]


class ActiveIn(BaseModel):
    active: bool


@router.put("/streamers/{sid}")
async def streamer_toggle(sid: int, body: ActiveIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        s = await session.get(Streamer, sid, with_for_update=True)
        if s is None:
            raise NotFound("Striminer")
        s.active = body.active
        out.user(s.user_id, "✅ Striminer sahifangiz qayta yoqildi." if body.active else "⛔️ Striminer sahifangiz admin tomonidan to'xtatildi.")
    await out.flush()
    return {"ok": True}


@router.get("/streamers/{sid}/donations")
async def streamer_donations(sid: int, admin: AdminUser, session: SessionDep):
    rows = await session.scalars(select(StreamDonation).where(StreamDonation.streamer_id == sid).order_by(StreamDonation.id.desc()).limit(100))
    return [{"id": d.id, "donor_id": d.donor_id, "name": d.donor_name, "kind": d.kind, "title": d.title, "amount": d.amount, "payout": d.payout,
             "message": d.message, "hidden": d.hidden, "at": _iso(d.created_at)} for d in rows]


@router.post("/stream-donations/{did}/hide")
async def stream_donation_hide(did: int, admin: AdminUser, session: SessionDep):
    """Nomaqbul xabarli donatni efirdan va sahifadan yashirish."""
    async with session.begin():
        d = await session.get(StreamDonation, did)
        if d is None:
            raise NotFound("Donat")
        d.hidden = True
    return {"ok": True}


# ================================================================ Pro auksionlar
@router.get("/pro/slots")
async def pro_slots(admin: AdminUser, session: SessionDep, status: str = "active"):
    stmt = select(ProSlot).order_by(ProSlot.id.desc()).limit(300)
    if status == "active":
        stmt = stmt.where(ProSlot.status.in_(("open", "sold", "disputed")))
    elif status != "all":
        stmt = stmt.where(ProSlot.status == status)
    rows = list(await session.scalars(stmt))
    names = await _names(session, [x for r in rows for x in (r.pro_id, r.winner_id)])
    return [{"id": r.id, "title": r.title, "pro_id": r.pro_id, "pro": names.get(r.pro_id), "winner_id": r.winner_id, "winner": names.get(r.winner_id),
             "price": r.price, "bids": r.bids, "status": r.status, "ends_at": _iso(r.ends_at), "play_at": _iso(r.play_at), "dispute": r.dispute} for r in rows]


@router.post("/pro/slots/{sid}/cancel")
async def pro_slot_cancel(sid: int, admin: AdminUser, session: SessionDep):
    """Auksionni bekor qilish: eng yuqori stavka egasiga pul qaytadi."""
    from app.services import pro

    out = Outbox()
    async with session.begin():
        s = await session.get(ProSlot, sid)
        if s is None:
            raise NotFound("Auksion")
        if s.status not in ("open", "sold", "disputed"):
            raise BadState("Auksion yakunlangan")
        if s.status == "disputed":
            await pro.resolve(session, sid, False, out)
        else:
            await pro.cancel_slot(session, s.pro_id, sid, out)
    await out.flush()
    return {"ok": True}


@router.get("/pro/profiles")
async def pro_profiles(admin: AdminUser, session: SessionDep):
    rows = list(await session.scalars(select(ProProfile).order_by(ProProfile.status, ProProfile.created_at.desc()).limit(300)))
    return [{"user_id": p.user_id, "name": p.name, "rank": p.rank, "link": p.link, "bio": p.bio, "status": p.status, "note": p.note} for p in rows]


# ================================================================ Birgalikda to'lov / Orzu
@router.get("/splits")
async def splits_list(admin: AdminUser, session: SessionDep, status: str = "open"):
    stmt = select(Split).order_by(Split.id.desc()).limit(300)
    if status != "all":
        stmt = stmt.where(Split.status == status)
    rows = list(await session.scalars(stmt))
    names = await _names(session, [r.creator_id for r in rows])
    counts = dict((await session.execute(select(SplitPart.split_id, func.count()).where(SplitPart.amount > 0).group_by(SplitPart.split_id))).all())
    return [{"id": r.id, "code": r.code, "mode": r.mode, "title": r.title, "creator_id": r.creator_id, "creator": names.get(r.creator_id),
             "target": r.target, "collected": r.collected, "parts": int(counts.get(r.id, 0)), "status": r.status, "expires_at": _iso(r.expires_at),
             "order_id": r.order_id} for r in rows]


@router.post("/splits/{code}/cancel")
async def split_cancel(code: str, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        s = await session.scalar(select(Split).where(Split.code == code))
        if s is None:
            raise NotFound("Yig'ish")
        await split.cancel(session, s.creator_id, code, out)
    await out.flush()
    return {"ok": True}


# ================================================================ Draft Jang
@router.get("/duels")
async def duels_list(admin: AdminUser, session: SessionDep):
    rows = list(await session.scalars(select(DraftDuel).order_by(DraftDuel.id.desc()).limit(200)))
    names = await _names(session, [x for r in rows for x in (r.a_id, r.b_id)])
    return [{"id": r.id, "code": r.code, "a": names.get(r.a_id), "b": names.get(r.b_id), "status": r.status, "a_score": r.a_score, "b_score": r.b_score,
             "winner": names.get(r.winner_id), "at": _iso(r.created_at)} for r in rows]


class EloIn(BaseModel):
    elo: int = Field(ge=0, le=5000)


@router.put("/elo/{user_id}")
async def set_elo(user_id: int, body: EloIn, admin: AdminUser, session: SessionDep):
    """Draft ELO ni qo'lda tuzatish (masalan, nohalol jang aniqlansa)."""
    async with session.begin():
        u = await session.get(User, user_id, with_for_update=True)
        if u is None:
            raise NotFound("Foydalanuvchi")
        u.draft_elo = body.elo
    return {"ok": True}


# ================================================================ Identifikatsiya (KYC)
@router.get("/kyc")
async def kyc_list(admin: AdminUser, session: SessionDep, status: str = "pending", q: str = ""):
    stmt = select(User).where(User.kyc_status == status).order_by(User.kyc_at.desc().nullslast()).limit(300)
    if q.strip():
        s = q.strip().lstrip("@").lower()
        stmt = stmt.where(or_(func.lower(User.username).like(f"%{s}%"), func.lower(User.first_name).like(f"%{s}%"),
                              User.id == int(s) if s.isdigit() else False))
    rows = await session.scalars(stmt)
    totals = dict((await session.execute(select(User.kyc_status, func.count()).group_by(User.kyc_status))).all())
    return {"totals": {k: int(totals.get(k, 0)) for k in ("pending", "verified", "rejected", "none")},
            "items": [{"id": u.id, "name": u.first_name, "username": u.username, "status": u.kyc_status, "note": u.kyc_note, "at": _iso(u.kyc_at)} for u in rows]}


class KycActionIn(BaseModel):
    action: str = Field(pattern="^(approve|reject|reset)$")
    note: str = Field("", max_length=300)


@router.post("/kyc/{user_id}")
async def kyc_action(user_id: int, body: KycActionIn, admin: AdminUser, session: SessionDep):
    """Tasdiqlash / rad etish (istalgan holatdan) yoki bekor qilish (qayta topshirishi kerak bo'ladi)."""
    out = Outbox()
    async with session.begin():
        u = await session.get(User, user_id, with_for_update=True)
        if u is None:
            raise NotFound("Foydalanuvchi")
        if body.action == "approve":
            u.kyc_status, u.kyc_note = "verified", None
            out.user(u.id, "✅ Shaxsingiz tasdiqlandi! Endi akkaunt savdo, ijara va pul yechish ochiq.")
        elif body.action == "reject":
            u.kyc_status, u.kyc_note = "rejected", (body.note or "Rasmlar aniq emas yoki talabga mos emas")
            out.user(u.id, f"❌ Identifikatsiya rad etildi.\nSabab: {u.kyc_note}\nRasmlarni qaytadan yuborishingiz mumkin.")
        else:
            u.kyc_status, u.kyc_note = "none", (body.note or None)
            out.user(u.id, "ℹ️ Identifikatsiyangiz bekor qilindi. Kerak bo'lsa, qaytadan topshiring." + (f"\nSabab: {body.note}" if body.note else ""))
        u.kyc_at = _now()
    await out.flush()
    return {"ok": True, "status": u.kyc_status}
