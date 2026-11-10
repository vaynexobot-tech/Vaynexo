from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api import schemas as S
from app.api.deps import AdminUser, SessionDep
from app.api.donate import invalidate_packages_cache
from app.errors import AppError, BadState, NotFound
from app.models import (
    BoostOrder, Deal, DonateOrder, DonatePackage, IncomingPayment, Listing, TgOrder, Topup, Tournament,
    TournamentEntry, User, Withdrawal,
)
from app.queue import enqueue
from app.services import donate as donate_svc
from app.services import app_settings, market, p2p, wallet
from app.services import services as svc
from app.services.notify import Outbox

router = APIRouter(prefix="/admin", tags=["admin"])


def _count(model, *where):
    return select(func.count()).select_from(model).where(*where)


@router.get("/stats")
async def stats(admin: AdminUser, session: SessionDep):
    day = datetime.now(timezone.utc) - timedelta(days=1)
    q = {
        "users": _count(User),
        "users_today": _count(User, User.created_at >= day),
        "moderation": _count(Listing, Listing.status == "moderation"),
        "withdrawals": _count(Withdrawal, Withdrawal.status == "pending"),
        "unmatched": _count(IncomingPayment, IncomingPayment.status == "unmatched"),
        "disputes": _count(Deal, Deal.status == "disputed"),
        "donate_review": _count(DonateOrder, DonateOrder.status == "review"),
        "tg_pending": _count(TgOrder, TgOrder.status == "processing"),
        "boost_open": _count(BoostOrder, BoostOrder.status.in_(("searching", "disputed"))),
    }
    out = {k: (await session.scalar(v)) or 0 for k, v in q.items()}
    out["topups_today"] = int(await session.scalar(select(func.coalesce(func.sum(Topup.pay_amount), 0)).where(Topup.status == "paid", Topup.paid_at >= day)))
    out["donate_today"] = int(await session.scalar(select(func.coalesce(func.sum(DonateOrder.price), 0)).where(DonateOrder.status == "done", DonateOrder.created_at >= day)))
    out["balances_total"] = int(await session.scalar(select(func.coalesce(func.sum(User.balance), 0))))
    return out


# ------------------------------------------------------------------ e'lonlar
@router.get("/listings")
async def listings(admin: AdminUser, session: SessionDep, status: str = "moderation"):
    rows = await session.scalars(select(Listing).where(Listing.status == status).order_by(Listing.id).limit(50))
    return [S.listing_full(x) for x in rows]


class ModerateIn(BaseModel):
    approve: bool
    reason: str = Field("", max_length=300)


@router.post("/listings/{listing_id}/moderate")
async def moderate(listing_id: int, body: ModerateIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        item = await market.moderate_listing(session, listing_id, body.approve, body.reason, out)
    await out.flush()
    return S.listing_card(item)


# ------------------------------------------------------------------ pul yechish
@router.get("/withdrawals")
async def withdrawals(admin: AdminUser, session: SessionDep, status: str = "pending"):
    rows = await session.scalars(select(Withdrawal).where(Withdrawal.status == status).order_by(Withdrawal.id).limit(100))
    return [S.withdrawal(w, full_card=True) for w in rows]


class ResolveIn(BaseModel):
    action: str
    note: str = Field("", max_length=300)


@router.post("/withdrawals/{w_id}")
async def resolve_withdrawal(w_id: int, body: ResolveIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        w = await svc.resolve_withdrawal(session, w_id, body.action, body.note, out)
    await out.flush()
    return S.withdrawal(w, full_card=True)


# ------------------------------------------------------------------ P2P kirimlar
@router.get("/incoming")
async def incoming(admin: AdminUser, session: SessionDep, status: str = "unmatched"):
    rows = await session.scalars(select(IncomingPayment).where(IncomingPayment.status == status).order_by(IncomingPayment.id.desc()).limit(100))
    return [{"id": i.id, "amount": i.amount, "source": i.source, "raw_text": i.raw_text, "status": i.status,
             "topup_id": i.topup_id, "created_at": S.iso(i.created_at)} for i in rows]


@router.get("/topups")
async def topups(admin: AdminUser, session: SessionDep, amount: int | None = None, user_id: int | None = None):
    stmt = select(Topup).where(Topup.status != "paid").order_by(Topup.id.desc()).limit(50)
    if amount:
        stmt = stmt.where(Topup.pay_amount.between(amount - 1000, amount + 1000))
    if user_id:
        stmt = stmt.where(Topup.user_id == user_id)
    return [{**S.topup(t, "", ""), "user_id": t.user_id} for t in await session.scalars(stmt)]


class ManualIncomingIn(BaseModel):
    amount: int | None = Field(None, gt=0)
    text: str | None = Field(None, max_length=2000)


@router.post("/incoming")
async def add_incoming(body: ManualIncomingIn, admin: AdminUser, session: SessionDep):
    """Admin bank xabarini qo'lda kiritadi (yoki summani yozadi)."""
    amount = body.amount or (p2p.parse_bank_message(body.text) if body.text else None)
    if not amount:
        raise AppError("bad_amount", "Matndan kirim summasi topilmadi — summani qo'lda kiriting")
    out = Outbox()
    async with session.begin():
        inc = await p2p.register_incoming(session, amount, "admin", out, raw_text=body.text,
                                          external_id=f"admin:{admin.id}:{amount}:{body.text or datetime.now().isoformat()}")
    await out.flush()
    if inc is None:
        raise BadState("Bu xabar allaqachon kiritilgan")
    return {"id": inc.id, "amount": inc.amount, "status": inc.status}


class AssignIn(BaseModel):
    topup_id: int


@router.post("/incoming/{incoming_id}/assign")
async def assign(incoming_id: int, body: AssignIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await p2p.assign_incoming(session, incoming_id, body.topup_id, out)
    await out.flush()
    return {"ok": True}


@router.post("/incoming/{incoming_id}/ignore")
async def ignore(incoming_id: int, admin: AdminUser, session: SessionDep):
    async with session.begin():
        inc = await session.get(IncomingPayment, incoming_id)
        if inc is None or inc.status != "unmatched":
            raise NotFound("Kirim")
        inc.status = "ignored"
    return {"ok": True}


# ------------------------------------------------------------------ nizolar
@router.get("/deals")
async def deals(admin: AdminUser, session: SessionDep, status: str = "disputed"):
    rows = await session.scalars(select(Deal).where(Deal.status == status).order_by(Deal.id).limit(50))
    return [S.deal(d, admin.id, market.credentials_for(d, admin.id, True)) for d in rows]


class DisputeResolveIn(BaseModel):
    winner: str = Field(pattern="^(buyer|seller)$")
    note: str = Field("", max_length=300)


@router.post("/deals/{deal_id}/resolve")
async def resolve_deal(deal_id: int, body: DisputeResolveIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        d = await market.resolve_dispute(session, deal_id, body.winner, body.note, out)
    await out.flush()
    return S.deal(d, admin.id)


# ------------------------------------------------------------------ donat / TG / boost
@router.get("/donate")
async def donate_orders(admin: AdminUser, session: SessionDep, status: str = "review"):
    rows = await session.scalars(select(DonateOrder).where(DonateOrder.status == status).order_by(DonateOrder.id.desc()).limit(100))
    return [{**S.donate_order(o), "user_id": o.user_id, "provider_ref": o.provider_ref, "attempts": o.attempts} for o in rows]


@router.post("/donate/{order_id}")
async def donate_resolve(order_id: int, body: ResolveIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    if body.action == "retry":
        async with session.begin():
            o = await session.get(DonateOrder, order_id)
            if o is None or o.status != "review":
                raise BadState("Faqat tekshiruvdagi buyurtmani qayta yuborish mumkin")
            o.status, o.attempts = "processing", 0
        await enqueue("fulfil_donate", order_id, "check")
        return {"ok": True}
    async with session.begin():
        o = await donate_svc.admin_resolve(session, order_id, body.action, out)
    await out.flush()
    return S.donate_order(o)


@router.get("/tg")
async def tg_orders(admin: AdminUser, session: SessionDep, status: str = "processing"):
    rows = await session.scalars(select(TgOrder).where(TgOrder.status == status).order_by(TgOrder.id).limit(100))
    return [S.tg_order(o) for o in rows]


@router.post("/tg/{order_id}")
async def tg_resolve(order_id: int, body: ResolveIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        o = await svc.resolve_tg_order(session, order_id, body.action, body.note, out)
    await out.flush()
    return S.tg_order(o)


@router.get("/boost")
async def boost_orders(admin: AdminUser, session: SessionDep, status: str = "searching"):
    rows = await session.scalars(select(BoostOrder).where(BoostOrder.status == status).order_by(BoostOrder.id).limit(100))
    return [S.boost(o) for o in rows]


@router.post("/boost/{order_id}")
async def boost_resolve(order_id: int, body: ResolveIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        o = await svc.boost_admin_resolve(session, order_id, body.action, out)
    await out.flush()
    await enqueue("update_boost_post", o.id)
    return S.boost(o)


# ------------------------------------------------------------------ foydalanuvchilar
@router.get("/users")
async def users(admin: AdminUser, session: SessionDep, q: str = ""):
    stmt = select(User).order_by(User.created_at.desc()).limit(50)
    q = q.strip().lstrip("@")
    if q:
        conds = [User.username.ilike(f"%{q}%"), User.first_name.ilike(f"%{q}%")]
        if q.isdigit():
            conds.append(User.id == int(q))
        stmt = stmt.where(or_(*conds))
    return [{**S.user_private(u), "is_banned": u.is_banned, "created_at": S.iso(u.created_at)} for u in await session.scalars(stmt)]


class BanIn(BaseModel):
    banned: bool


@router.post("/users/{user_id}/ban")
async def ban(user_id: int, body: BanIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        u = await session.get(User, user_id)
        if u is None:
            raise NotFound("Foydalanuvchi")
        if u.id == admin.id:
            raise BadState("O'zingizni bloklay olmaysiz")
        u.is_banned = body.banned
    return {"ok": True}


class AdjustIn(BaseModel):
    amount: int  # + qo'shish, - ayirish
    note: str = Field(min_length=3, max_length=300)
    request_id: str = Field(min_length=8, max_length=64)  # ikki marta bosilsa ham bir marta bajariladi


@router.post("/users/{user_id}/balance")
async def adjust(user_id: int, body: AdjustIn, admin: AdminUser, session: SessionDep):
    if body.amount == 0:
        raise AppError("bad_amount", "Summa 0 bo'lmasin")
    out = Outbox()
    async with session.begin():
        e = await wallet.change_balance(session, user_id, body.amount, "admin_adjust", f"admin:{body.request_id}",
                                        ref_type="admin", ref_id=admin.id, note=body.note)
    if e:
        sign = "+" if body.amount > 0 else "−"
        out.user(user_id, f"💼 Balans o'zgardi: {sign}{abs(body.amount):,} so'm\nIzoh: {body.note}".replace(",", " "))
        await out.flush()
    return {"ok": True, "applied": e is not None}


# ------------------------------------------------------------------ paketlar
class PackageIn(BaseModel):
    game: str = Field(pattern="^(ML|MC)$")
    name: str = Field(max_length=64)
    diamonds: int = Field(0, ge=0)
    bonus: int = Field(0, ge=0)
    price: int = Field(gt=0)
    provider_sku: str = Field(max_length=64)
    is_active: bool = True
    is_hot: bool = False
    sort: int = 0


@router.get("/packages")
async def packages(admin: AdminUser, session: SessionDep):
    rows = await session.scalars(select(DonatePackage).order_by(DonatePackage.game, DonatePackage.sort, DonatePackage.price))
    return [S.package(p) for p in rows]


@router.post("/packages")
async def create_package(body: PackageIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        p = DonatePackage(**body.model_dump())
        session.add(p)
    await invalidate_packages_cache()
    return S.package(p)


@router.put("/packages/{pkg_id}")
async def update_package(pkg_id: int, body: PackageIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        p = await session.get(DonatePackage, pkg_id)
        if p is None:
            raise NotFound("Paket")
        for k, v in body.model_dump().items():
            setattr(p, k, v)
    await invalidate_packages_cache()
    return S.package(p)


# ------------------------------------------------------------------ turnirlar
class TournamentIn(BaseModel):
    title: str = Field(max_length=120)
    game: str = Field(pattern="^(ML|MC)$")
    prize_fund: int = Field(ge=0)
    entry_fee: int = Field(0, ge=0)
    max_players: int = Field(gt=1, le=4096)
    starts_at: datetime
    rules: str = Field("", max_length=5000)
    status: str = Field("open", pattern="^(open|running|finished)$")


@router.post("/tournaments")
async def create_tournament(body: TournamentIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        t = Tournament(**body.model_dump())
        session.add(t)
    return S.tournament(t)


@router.put("/tournaments/{t_id}")
async def update_tournament(t_id: int, body: TournamentIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        t = await session.get(Tournament, t_id)
        if t is None:
            raise NotFound("Turnir")
        for k, v in body.model_dump().items():
            setattr(t, k, v)
    return S.tournament(t)


@router.get("/tournaments/{t_id}/entries")
async def entries(t_id: int, admin: AdminUser, session: SessionDep):
    rows = await session.scalars(select(TournamentEntry).where(TournamentEntry.tournament_id == t_id).order_by(TournamentEntry.id))
    return [{"user_id": e.user_id, "nick": e.nick, "game_id": e.game_id, "server": e.server, "tg_username": e.tg_username} for e in rows]


# ------------------------------------------------------------------ sozlamalar
@router.get("/settings")
async def get_settings(admin: AdminUser, session: SessionDep):
    return await app_settings.get_all(session)


class SettingIn(BaseModel):
    key: str = Field(max_length=64)
    value: int


@router.put("/settings")
async def put_setting(body: SettingIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        await app_settings.set_value(session, body.key, body.value)
    return await app_settings.get_all(session)
