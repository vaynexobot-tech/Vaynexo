from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update

from app.api import schemas as S
from app.api.deps import CurrentUser, SessionDep, page_params
from app.errors import NotFound
from app.models import Chat, Deal, Listing, Message, Review
from app.services import market as svc
from app.services.notify import Outbox

router = APIRouter(tags=["market"])

COLLECTION_LEVELS = ["Amateur", "Junior", "Senior", "Expert", "Renowned", "Exalted", "Mega", "World"]


@router.get("/listings")
async def listings(
    user: CurrentUser,
    session: SessionDep,
    game: str | None = None,
    q: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_skins: int | None = None,
    level: str | None = None,
    rank: str | None = None,
    sort: str = "new",
    limit: int = 20,
    offset: int = 0,
):
    limit, offset = page_params(limit, offset)
    stmt = select(Listing).where(Listing.status == "active")
    if game in ("ML", "MC"):
        stmt = stmt.where(Listing.game == game)
    if q:
        like = f"%{q.strip()[:60]}%"
        stmt = stmt.where(or_(Listing.title.ilike(like), Listing.rank.ilike(like), Listing.description.ilike(like)))
    if min_price:
        stmt = stmt.where(Listing.price >= min_price)
    if max_price:
        stmt = stmt.where(Listing.price <= max_price)
    if min_skins:
        stmt = stmt.where(Listing.skins >= min_skins)
    if level:
        stmt = stmt.where(Listing.collection_level.ilike(f"{level[:20]}%"))
    if rank:
        stmt = stmt.where(Listing.rank.ilike(f"{rank[:20]}%"))
    order = {"cheap": Listing.price.asc(), "skins": Listing.skins.desc(), "expensive": Listing.price.desc()}.get(sort, Listing.id.desc())
    rows = await session.scalars(stmt.order_by(order, Listing.id.desc()).offset(offset).limit(limit + 1))
    rows = list(rows)
    return {"items": [S.listing_card(x) for x in rows[:limit]], "has_more": len(rows) > limit}


@router.get("/listings/{listing_id}")
async def listing_detail(listing_id: int, user: CurrentUser, session: SessionDep):
    item = await session.get(Listing, listing_id)
    if item is None or (item.status not in ("active", "reserved", "sold") and item.seller_id != user.id and not user.is_admin):
        raise NotFound("E'lon")
    if item.seller_id != user.id:
        await session.execute(update(Listing).where(Listing.id == listing_id).values(views=Listing.views + 1))
        await session.commit()
    stats = await svc.seller_stats(session, item.seller_id)
    chat_id = await session.scalar(select(Chat.id).where(Chat.listing_id == listing_id, Chat.buyer_id == user.id))
    return {**S.listing_full(item), "seller_stats": stats, "chat_id": chat_id, "is_mine": item.seller_id == user.id}


class ListingIn(BaseModel):
    game: str
    title: str = Field(max_length=120)
    rank: str = Field("", max_length=32)
    server: str = Field("", max_length=32)
    collection_level: str = Field("", max_length=32)
    skins: int = Field(0, ge=0)
    heroes: int = Field(0, ge=0)
    price: int = Field(gt=0)
    description: str = Field("", max_length=3000)
    media: list[dict] = []


@router.post("/listings")
async def create_listing(body: ListingIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        item = await svc.create_listing(session, user.id, body.model_dump(), out)
    await out.flush()
    return S.listing_card(item)


@router.put("/listings/{listing_id}")
async def update_listing(listing_id: int, body: ListingIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        item = await svc.update_listing(session, user.id, listing_id, body.model_dump())
    return S.listing_card(item)


@router.post("/listings/{listing_id}/close")
async def close_listing(listing_id: int, user: CurrentUser, session: SessionDep):
    async with session.begin():
        item = await svc.close_listing(session, user.id, listing_id)
    return S.listing_card(item)


@router.get("/my/listings")
async def my_listings(user: CurrentUser, session: SessionDep):
    rows = list(await session.scalars(select(Listing).where(Listing.seller_id == user.id).order_by(Listing.id.desc()).limit(100)))
    counts = dict(
        (await session.execute(
            select(Chat.listing_id, func.count()).where(Chat.listing_id.in_([x.id for x in rows] or [0])).group_by(Chat.listing_id)
        )).all()
    )
    return [{**S.listing_card(x), "views": x.views, "chats": counts.get(x.id, 0), "reject_reason": x.reject_reason} for x in rows]


# ------------------------------------------------------------------ chat
@router.post("/listings/{listing_id}/chat")
async def open_chat(listing_id: int, user: CurrentUser, session: SessionDep):
    async with session.begin():
        chat = await svc.open_chat(session, listing_id, user.id)
    return S.chat(chat, user.id)


@router.get("/chats")
async def chats(user: CurrentUser, session: SessionDep):
    rows = await session.scalars(
        select(Chat).where(or_(Chat.buyer_id == user.id, Chat.seller_id == user.id)).order_by(Chat.last_message_at.desc()).limit(50)
    )
    return [S.chat(c, user.id) for c in rows]


@router.get("/chats/{chat_id}")
async def chat_messages(chat_id: int, user: CurrentUser, session: SessionDep, after: int = 0):
    """Yangi xabarlar `after` dan keyin. Frontend chat ochiq bo'lganda har 3 soniyada so'raydi."""
    chat = await svc.get_chat_for(session, chat_id, user.id, user.is_admin)
    msgs = await session.scalars(
        select(Message).where(Message.chat_id == chat_id, Message.id > after).order_by(Message.id.asc()).limit(200)
    )
    deal = await session.scalar(select(Deal).where(Deal.chat_id == chat_id).order_by(Deal.id.desc()).limit(1))
    return {
        "chat": S.chat(chat, user.id),
        "messages": [S.message(m) for m in msgs],
        "deal": {"id": deal.id, "status": deal.status} if deal else None,
    }


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/chats/{chat_id}/messages")
async def post_message(chat_id: int, body: MessageIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        chat = await svc.get_chat_for(session, chat_id, user.id)
        msg = await svc.send_message(session, chat, user.id, body.text, out)
    await out.flush()
    return S.message(msg)


# ------------------------------------------------------------------ bitim
@router.post("/listings/{listing_id}/buy")
async def buy(listing_id: int, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        deal = await svc.buy(session, listing_id, user.id, out)
    await out.flush()
    return S.deal(deal, user.id)


@router.get("/deals")
async def deals(user: CurrentUser, session: SessionDep, role: str = "buyer"):
    col = Deal.seller_id if role == "seller" else Deal.buyer_id
    rows = await session.scalars(select(Deal).where(col == user.id).order_by(Deal.id.desc()).limit(50))
    return [S.deal(d, user.id) for d in rows]


@router.get("/deals/{deal_id}")
async def deal_detail(deal_id: int, user: CurrentUser, session: SessionDep):
    d = await session.get(Deal, deal_id)
    if d is None or (user.id not in (d.buyer_id, d.seller_id) and not user.is_admin):
        raise NotFound("Bitim")
    reviewed = await session.scalar(select(Review.id).where(Review.deal_id == deal_id))
    return {**S.deal(d, user.id, svc.credentials_for(d, user.id, user.is_admin)), "reviewed": bool(reviewed),
            "seller_deliver_hours": svc.SELLER_DELIVER_HOURS}


class DeliverIn(BaseModel):
    credentials: str = Field(min_length=3, max_length=2000)


@router.post("/deals/{deal_id}/deliver")
async def deliver(deal_id: int, body: DeliverIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        d = await svc.deliver(session, deal_id, user.id, body.credentials, out)
    await out.flush()
    return S.deal(d, user.id)


@router.post("/deals/{deal_id}/confirm")
async def confirm(deal_id: int, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        d = await svc.confirm(session, deal_id, user.id, out)
    await out.flush()
    return S.deal(d, user.id)


@router.post("/deals/{deal_id}/cancel")
async def cancel(deal_id: int, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        d = await svc.cancel(session, deal_id, user.id, out)
    await out.flush()
    return S.deal(d, user.id)


class DisputeIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


@router.post("/deals/{deal_id}/dispute")
async def dispute(deal_id: int, body: DisputeIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        d = await svc.open_dispute(session, deal_id, user.id, body.reason, out)
    await out.flush()
    return S.deal(d, user.id)


class ReviewIn(BaseModel):
    score: int = Field(ge=1, le=5)
    tags: list[str] = []
    text: str = Field("", max_length=500)


@router.post("/deals/{deal_id}/review")
async def review(deal_id: int, body: ReviewIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await svc.review(session, deal_id, user.id, body.score, body.tags, body.text)
    return {"ok": True}
