from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, select

from app.api import schemas as S
from app.api.deps import AdminUser, CurrentUser, SessionDep, page_params
from app.errors import NotFound
from app.models import Rental, RentListing
from app.services import rental as svc
from app.services.notify import Outbox

router = APIRouter(tags=["rent"])


def card(x: RentListing) -> dict:
    now = datetime.now(timezone.utc)
    owner = x.__dict__.get("owner")
    return {
        "id": x.id, "game": x.game, "title": x.title, "rank": x.rank, "server": x.server, "collection_level": x.collection_level, "skins": x.skins, "heroes": x.heroes,
        "price_per_hour": x.price_per_hour, "status": x.status, "reject_reason": x.reject_reason,
        "cover": next((m["url"] for m in x.media if m.get("type") == "image"), None),
        "busy_until": S.iso(x.busy_until) if x.busy_until and x.busy_until > now else None,
        "owner_rating": round(owner.rating_sum / owner.rating_count, 1) if owner and owner.rating_count else None,
        "created_at": S.iso(x.created_at),
    }


def full(x: RentListing) -> dict:
    return {**card(x), "description": x.description, "media": x.media, "owner": S.user_public(x.owner)}


def rental_view(r: Rental, me: int, is_admin: bool = False) -> dict:
    return {
        "id": r.id, "listing": card(r.listing), "role": "renter" if r.renter_id == me else ("owner" if r.owner_id == me else "admin"),
        "hours": r.hours, "duration": svc.DURATIONS.get(r.hours, f"{r.hours} soat"), "price": r.price, "deposit": r.deposit,
        "commission": r.commission, "status": r.status, "starts_at": S.iso(r.starts_at), "ends_at": S.iso(r.ends_at),
        "review_until": S.iso(r.review_until), "dispute_by": r.dispute_by, "dispute_reason": r.dispute_reason,
        "resolution": r.resolution, "credentials": svc.credentials_for(r, me, is_admin), "renter_id": r.renter_id, "owner_id": r.owner_id,
    }


@router.get("/rent/config")
async def rent_config(user: CurrentUser, session: SessionDep):
    return await svc.config(session)


@router.get("/rent/listings")
async def listings(user: CurrentUser, session: SessionDep, free: bool = False, rank: str | None = None, max_price: int | None = None,
                   level: str | None = None,
                   sort: str = "cheap", limit: int = 20, offset: int = 0):
    limit, offset = page_params(limit, offset)
    stmt = select(RentListing).where(RentListing.status == "active")
    if free:
        stmt = stmt.where(or_(RentListing.busy_until.is_(None), RentListing.busy_until <= func.now()))
    if rank:
        stmt = stmt.where(RentListing.rank.ilike(f"{rank[:20]}%"))
    if max_price:
        stmt = stmt.where(RentListing.price_per_hour <= max_price)
    if level:
        stmt = stmt.where(RentListing.collection_level.ilike(f"{level[:20]}%"))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    free_first = case((or_(RentListing.busy_until.is_(None), RentListing.busy_until <= func.now()), 0), else_=1)
    order = {"expensive": RentListing.price_per_hour.desc(), "new": RentListing.id.desc(), "skins": RentListing.skins.desc()}.get(
        sort, RentListing.price_per_hour.asc())
    rows = list(await session.scalars(stmt.order_by(free_first, order, RentListing.id.desc()).offset(offset).limit(limit + 1)))
    free_count = await session.scalar(
        select(func.count()).select_from(RentListing).where(
            RentListing.status == "active", or_(RentListing.busy_until.is_(None), RentListing.busy_until <= func.now()))
    )
    return {"items": [card(x) for x in rows[:limit]], "has_more": len(rows) > limit, "total": total or 0, "free": free_count or 0}


@router.get("/rent/listings/{lid}")
async def listing(lid: int, user: CurrentUser, session: SessionDep):
    x = await session.get(RentListing, lid)
    if x is None or (x.status != "active" and x.owner_id != user.id and not user.is_admin):
        raise NotFound("E'lon")
    return {**full(x), "is_mine": x.owner_id == user.id}


class RentListingIn(BaseModel):
    game: str
    title: str = Field(max_length=120)
    rank: str = Field("", max_length=32)
    server: str = Field("", max_length=32)
    collection_level: str = Field("", max_length=32)
    skins: int = Field(0, ge=0)
    heroes: int = Field(0, ge=0)
    price_per_hour: int = Field(gt=0)
    description: str = Field("", max_length=3000)
    media: list[dict] = []
    credentials: str = Field("", max_length=2000)


@router.post("/rent/listings")
async def create(body: RentListingIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        x = await svc.create_listing(session, user.id, body.model_dump(), out)
    await out.flush()
    return card(x)


@router.put("/rent/listings/{lid}")
async def update(lid: int, body: RentListingIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        x = await svc.update_listing(session, user.id, lid, body.model_dump())
    return card(x)


@router.post("/rent/listings/{lid}/close")
async def close(lid: int, user: CurrentUser, session: SessionDep):
    async with session.begin():
        x = await svc.close_listing(session, user.id, lid)
    return card(x)


@router.get("/my/rent-listings")
async def my_listings(user: CurrentUser, session: SessionDep):
    rows = await session.scalars(select(RentListing).where(RentListing.owner_id == user.id).order_by(RentListing.id.desc()).limit(100))
    return [card(x) for x in rows]


class RentIn(BaseModel):
    hours: int


@router.post("/rent/listings/{lid}/rent")
async def rent(lid: int, body: RentIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        r = await svc.rent(session, lid, user.id, body.hours, out)
    await out.flush()
    return rental_view(r, user.id)


@router.get("/rentals")
async def rentals(user: CurrentUser, session: SessionDep, role: str = "renter"):
    col = Rental.owner_id if role == "owner" else Rental.renter_id
    rows = await session.scalars(select(Rental).where(col == user.id).order_by(Rental.id.desc()).limit(50))
    return [rental_view(r, user.id) for r in rows]


@router.get("/rentals/{rid}")
async def rental(rid: int, user: CurrentUser, session: SessionDep):
    r = await session.get(Rental, rid)
    if r is None or (user.id not in (r.renter_id, r.owner_id) and not user.is_admin):
        raise NotFound("Ijara")
    return rental_view(r, user.id, user.is_admin)


@router.post("/rentals/{rid}/confirm")
async def confirm(rid: int, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        r = await svc.owner_confirm(session, rid, user.id, out)
    await out.flush()
    return rental_view(r, user.id)


class DisputeIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


@router.post("/rentals/{rid}/dispute")
async def dispute(rid: int, body: DisputeIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        r = await svc.open_dispute(session, rid, user.id, body.reason, out)
    await out.flush()
    return rental_view(r, user.id)


# ------------------------------------------------------------------ admin
@router.get("/admin/rent/listings")
async def admin_listings(admin: AdminUser, session: SessionDep, status: str = "moderation"):
    rows = await session.scalars(select(RentListing).where(RentListing.status == status).order_by(RentListing.id).limit(50))
    return [full(x) for x in rows]


class ModerateIn(BaseModel):
    approve: bool
    reason: str = Field("", max_length=300)


@router.post("/admin/rent/listings/{lid}/moderate")
async def admin_moderate(lid: int, body: ModerateIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        x = await svc.moderate(session, lid, body.approve, body.reason, out)
    await out.flush()
    return card(x)


@router.get("/admin/rentals")
async def admin_rentals(admin: AdminUser, session: SessionDep, status: str = "disputed"):
    rows = await session.scalars(select(Rental).where(Rental.status == status).order_by(Rental.id).limit(50))
    return [rental_view(r, admin.id, True) for r in rows]


class ResolveIn(BaseModel):
    decision: str = Field(pattern="^(owner|renter|normal)$")
    note: str = Field("", max_length=300)


@router.post("/admin/rentals/{rid}/resolve")
async def admin_resolve(rid: int, body: ResolveIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        r = await svc.resolve(session, rid, body.decision, body.note, out)
    await out.flush()
    return rental_view(r, admin.id, True)
