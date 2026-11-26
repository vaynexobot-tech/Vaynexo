"""Premium bo'limlar API: VAYNEXO Plus, Skin jamg'armasi, signallar, efirda donat, Pro bilan o'yna."""

from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.deps import AdminUser, CurrentUser, SessionDep, rate_limit
from app.config import settings
from app.queue import enqueue
from app.services import plus, pro, savings, signals, stream, vay
from app.services.notify import Outbox

router = APIRouter(tags=["premium"])
public_router = APIRouter(tags=["premium"])  # vidjet (OBS) — Telegram avtorizatsiyasisiz, maxfiy token bilan


# ================================================================ VAY ball
@router.get("/vay")
async def vay_get(user: CurrentUser, session: SessionDep):
    return await vay.overview(session, user)


# ================================================================ VAYNEXO Plus
@router.get("/plus")
async def plus_get(user: CurrentUser, session: SessionDep):
    return await plus.overview(session, user.id)


@router.post("/plus/buy")
async def plus_buy(user: CurrentUser, session: SessionDep):
    async with session.begin():
        await plus.buy(session, user.id)
    return await plus.overview(session, user.id)


class PlusOpts(BaseModel):
    auto_renew: bool | None = None
    package_id: int | None = None
    player_id: str = Field("", max_length=64)
    zone_id: str = Field("", max_length=64)
    clear_auto: bool = False


@router.put("/plus")
async def plus_set(body: PlusOpts, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await plus.set_options(session, user.id, body.auto_renew, body.package_id, body.player_id, body.zone_id, body.clear_auto)
    return await plus.overview(session, user.id)


# ================================================================ Skin jamg'armasi
@router.get("/savings")
async def savings_get(user: CurrentUser, session: SessionDep):
    return await savings.overview(session, user.id)


class SavingIn(BaseModel):
    package_id: int
    player_id: str = Field("", max_length=64)
    zone_id: str = Field("", max_length=64)
    weekly: int = Field(0, ge=0, le=100_000_000)
    first: int = Field(0, ge=0, le=100_000_000)
    buy_at: datetime | None = None


@router.post("/savings")
async def savings_create(body: SavingIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await savings.create(session, user.id, body.package_id, body.player_id, body.zone_id, body.weekly, body.first, body.buy_at)
    return await savings.overview(session, user.id)


class AmountIn(BaseModel):
    amount: int = Field(ge=1, le=100_000_000)


@router.post("/savings/{sid}/deposit")
async def savings_deposit(sid: int, body: AmountIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await savings.deposit(session, user.id, sid, body.amount)
    return await savings.overview(session, user.id)


@router.post("/savings/{sid}/cancel")
async def savings_cancel(sid: int, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await savings.cancel(session, user.id, sid)
    return await savings.overview(session, user.id)


@router.post("/savings/{sid}/buy")
async def savings_buy(sid: int, user: CurrentUser, session: SessionDep):
    async with session.begin():
        order = await savings.buy(session, user.id, sid)
        oid = order.id
    await enqueue("fulfil_donate", oid, "create")
    return {"order_id": oid, **(await savings.overview(session, user.id))}


# ================================================================ signallar
@router.get("/signals")
async def signals_get(user: CurrentUser, session: SessionDep):
    return {"double": await signals.is_on(session, user.id, "double")}


class SignalIn(BaseModel):
    on: bool


@router.put("/signals/{kind}")
async def signals_set(kind: str, body: SignalIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await signals.set_on(session, user.id, kind, body.on)
    return {kind: body.on}


@router.get("/admin/signals")
async def admin_signals(admin: AdminUser, session: SessionDep):
    return {"subscribers": await signals.count(session, "double"), "default_text": signals.DEFAULT_TEXT,
            "history": await signals.history(session, "double")}


class BroadcastIn(BaseModel):
    text: str = Field("", max_length=1000)


@router.post("/admin/signals/double")
async def admin_signal_send(body: BroadcastIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        n = await signals.broadcast(session, "double", body.text, out)
    await out.flush()
    return {"sent": n}


# ================================================================ efirda donat
@router.get("/stream/me")
async def stream_me(user: CurrentUser, session: SessionDep):
    return await stream.dashboard(session, user.id, settings.bot_username, settings.webapp_url)


class StreamerIn(BaseModel):
    slug: str = Field("", max_length=32)
    name: str = Field(max_length=64)
    about: str = Field("", max_length=200)
    player_id: str = Field(max_length=32)
    zone_id: str = Field(max_length=16)


@router.post("/stream/me")
async def stream_register(body: StreamerIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await stream.register(session, user.id, body.slug, body.name, body.about, body.player_id, body.zone_id)
    return await stream.dashboard(session, user.id, settings.bot_username, settings.webapp_url)


@router.post("/stream/me/test")
async def stream_test(user: CurrentUser, session: SessionDep):
    await rate_limit(f"stest:{user.id}", limit=10, window=600)
    async with session.begin():
        await stream.test_alert(session, user.id)
    return {"ok": True}


@router.post("/stream/me/rotate")
async def stream_rotate(user: CurrentUser, session: SessionDep):
    async with session.begin():
        await stream.rotate_token(session, user.id)
    return await stream.dashboard(session, user.id, settings.bot_username, settings.webapp_url)


@router.post("/stream/me/hide/{did}")
async def stream_hide(did: int, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await stream.hide(session, user.id, did)
    return {"ok": True}


@router.get("/stream/s/{slug}")
async def stream_page(slug: str, user: CurrentUser, session: SessionDep):
    return await stream.public_page(session, slug)


class StreamDonateIn(BaseModel):
    kind: str = Field(pattern="^(pack|money)$")
    package_id: int | None = None
    amount: int = Field(0, ge=0, le=10_000_000)
    message: str = Field("", max_length=300)
    anon: bool = False


@router.post("/stream/s/{slug}/donate")
async def stream_donate(slug: str, body: StreamDonateIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"sdon:{user.id}", limit=20, window=600)
    out = Outbox()
    oid = None
    async with session.begin():
        if body.kind == "pack":
            d = await stream.donate_pack(session, user, slug, body.package_id or 0, body.message, body.anon, out)
            oid = d.order_id
        else:
            await stream.donate_money(session, user, slug, body.amount, body.message, body.anon, out)
    await out.flush()
    if oid:
        await enqueue("fulfil_donate", oid, "create")
    return {"ok": True, "order_id": oid}


@public_router.get("/stream/feed/{token}")
async def stream_feed(token: str, session: SessionDep, after: int = -1):
    return await stream.feed(session, token, after)


@public_router.get("/stream/w/{token}", response_class=HTMLResponse)
async def stream_widget(token: str, session: SessionDep):
    await stream.feed(session, token, -1)  # token tekshiruvi
    return HTMLResponse(stream.WIDGET_HTML, headers={"Cache-Control": "no-store"})


# ================================================================ Pro bilan o'yna
@router.get("/pro")
async def pro_list(user: CurrentUser, session: SessionDep):
    return {"items": await pro.list_open(session, user.id)}


@router.get("/pro/my")
async def pro_my(user: CurrentUser, session: SessionDep):
    return await pro.my(session, user.id)


@router.get("/pro/{sid}")
async def pro_detail(sid: int, user: CurrentUser, session: SessionDep):
    return await pro.detail(session, sid, user.id)


class ProApplyIn(BaseModel):
    name: str = Field(max_length=64)
    bio: str = Field("", max_length=300)
    link: str = Field("", max_length=200)
    rank: str = Field("", max_length=32)


@router.post("/pro/apply")
async def pro_apply(body: ProApplyIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"papply:{user.id}", limit=5, window=3600)
    out = Outbox()
    async with session.begin():
        await pro.apply(session, user.id, body.name, body.bio, body.link, body.rank, out)
    await out.flush()
    return await pro.my(session, user.id)


class SlotIn(BaseModel):
    title: str = Field(max_length=120)
    details: str = Field("", max_length=500)
    play_at: datetime
    ends_at: datetime
    min_bid: int = Field(ge=1, le=100_000_000)
    step: int = Field(ge=1, le=10_000_000)


@router.post("/pro/slots")
async def pro_create(body: SlotIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        s = await pro.create_slot(session, user.id, body.title, body.details, body.play_at, body.ends_at, body.min_bid, body.step, out)
        sid = s.id
    await out.flush()
    return await pro.detail(session, sid, user.id)


@router.post("/pro/{sid}/bid")
async def pro_bid(sid: int, body: AmountIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"pbid:{user.id}", limit=30, window=600)
    out = Outbox()
    async with session.begin():
        await pro.place_bid(session, user.id, sid, body.amount, out)
    await out.flush()
    return await pro.detail(session, sid, user.id)


@router.post("/pro/{sid}/cancel")
async def pro_cancel(sid: int, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await pro.cancel_slot(session, user.id, sid, out)
    await out.flush()
    return await pro.detail(session, sid, user.id)


@router.post("/pro/{sid}/confirm")
async def pro_confirm(sid: int, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await pro.confirm(session, user.id, sid, out)
    await out.flush()
    return await pro.detail(session, sid, user.id)


class DisputeIn(BaseModel):
    reason: str = Field("", max_length=300)


@router.post("/pro/{sid}/dispute")
async def pro_dispute(sid: int, body: DisputeIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await pro.dispute(session, user.id, sid, body.reason, out)
    await out.flush()
    return await pro.detail(session, sid, user.id)


@router.get("/admin/pro")
async def admin_pro(admin: AdminUser, session: SessionDep):
    return await pro.admin_lists(session)


class ReviewIn(BaseModel):
    approve: bool
    note: str = Field("", max_length=200)


@router.post("/admin/pro/apps/{uid}")
async def admin_pro_review(uid: int, body: ReviewIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await pro.review(session, uid, body.approve, body.note, out)
    await out.flush()
    return await pro.admin_lists(session)


class ResolveIn(BaseModel):
    pay: bool


@router.post("/admin/pro/disputes/{sid}")
async def admin_pro_resolve(sid: int, body: ResolveIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await pro.resolve(session, sid, body.pay, out)
    await out.flush()
    return await pro.admin_lists(session)
