from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update

from app.api import schemas as S
from app.api.deps import AdminUser, SessionDep, rate_limit
from app.api.donate import invalidate_packages_cache
from app.config import settings
from app.db import SessionLocal
from app.errors import AppError, BadState, NotFound
from app.models import (
    Rental, RentListing,
    BoostOrder, Deal, DonateGame, DonateOrder, DonatePackage, DonateProvider, IncomingPayment, Listing, P2PCard, PartnerVideo, TgOrder, Topup, Tournament,
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
        "rent_moderation": _count(RentListing, RentListing.status == "moderation"),
        "rent_disputes": _count(Rental, Rental.status == "disputed"),
        "topup_checking": _count(Topup, Topup.status == "checking"),
        "kyc_pending": _count(User, User.kyc_status == "pending"),
        "partner_pending": _count(PartnerVideo, PartnerVideo.status == "pending"),
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
    if body.approve and not settings.dev_mode:  # kanalga darhol (aks holda 1 daqiqa ichida cron chiqaradi)
        import asyncio

        from app.services import channel

        asyncio.create_task(channel.sync_batch())
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


@router.get("/p2p/sms-setup")
async def sms_setup(admin: AdminUser, session: SessionDep):
    """SMS-forwarder ilovasini ulash uchun ma'lumot (faqat admin ko'radi)."""
    base = settings.webapp_url.rstrip("/")
    last = await session.scalar(select(IncomingPayment).where(IncomingPayment.source == "sms").order_by(IncomingPayment.id.desc()).limit(1))
    since = datetime.now(timezone.utc) - timedelta(days=1)
    rows = (await session.execute(
        select(IncomingPayment.source, func.count()).where(IncomingPayment.created_at >= since).group_by(IncomingPayment.source)
    )).all()
    ready = settings.p2p_secret != "change-me"
    return {"url": f"{base}/api/p2p/incoming", "url_with_key": f"{base}/api/p2p/incoming?key={settings.p2p_secret}" if ready else None,
            "secret": settings.p2p_secret if ready else None, "header": "X-P2P-Secret", "ready": ready,
            "body_template": '{"text": "%text%", "from": "%from%", "id": "%sentStamp%"}',
            "last_sms_at": S.iso(last.created_at) if last else None, "last_sms_amount": last.amount if last else None,
            "last_24h": {src: n for src, n in rows}}


@router.get("/topups/checking")
async def topups_checking(admin: AdminUser, session: SessionDep):
    rows = list(await session.scalars(select(Topup).where(Topup.status == "checking").order_by(Topup.claimed_at).limit(100)))
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_({t.user_id for t in rows} or {0})))}
    return [{**S.topup(t, "", ""), "user_id": t.user_id,
             "user_name": (users[t.user_id].username or users[t.user_id].first_name) if t.user_id in users else ""} for t in rows]


class RejectIn(BaseModel):
    reason: str | None = Field(None, max_length=300)


@router.post("/topups/{topup_id}/confirm")
async def topup_confirm(topup_id: int, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        t = await p2p.admin_confirm(session, topup_id, out)
    await out.flush()
    return {**S.topup(t, "", ""), "user_id": t.user_id}


@router.post("/topups/{topup_id}/reject")
async def topup_reject(topup_id: int, body: RejectIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        t = await p2p.admin_reject(session, topup_id, body.reason, out)
    await out.flush()
    return {**S.topup(t, "", ""), "user_id": t.user_id}


# ------------------------------------------------------------------ to'lov kartalari
class P2PCardIn(BaseModel):
    number: str = Field(max_length=32)
    holder: str = Field("", max_length=64)
    active: bool = True
    sort: int = 0


def _card(c: P2PCard) -> dict:
    return {"id": c.id, "number": c.number, "holder": c.holder, "kind": c.kind, "active": c.active, "sort": c.sort}


@router.get("/p2p-cards")
async def p2p_cards(admin: AdminUser, session: SessionDep):
    return [_card(c) for c in await session.scalars(select(P2PCard).order_by(P2PCard.sort, P2PCard.id))]


@router.post("/p2p-cards")
async def p2p_card_add(body: P2PCardIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        number = p2p.clean_card(body.number)
        c = P2PCard(number=number, holder=body.holder.strip().upper(), kind=p2p.card_kind(number), active=body.active, sort=body.sort)
        session.add(c)
    return _card(c)


@router.put("/p2p-cards/{card_id}")
async def p2p_card_update(card_id: int, body: P2PCardIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        c = await session.get(P2PCard, card_id)
        if c is None:
            raise NotFound("Karta")
        c.number = p2p.clean_card(body.number)
        c.holder, c.kind, c.active, c.sort = body.holder.strip().upper(), p2p.card_kind(c.number), body.active, body.sort
    return _card(c)


@router.delete("/p2p-cards/{card_id}")
async def p2p_card_delete(card_id: int, admin: AdminUser, session: SessionDep):
    async with session.begin():
        c = await session.get(P2PCard, card_id)
        if c is not None:
            await session.delete(c)
    return {"ok": True}


class ManualIncomingIn(BaseModel):
    amount: int | None = Field(None, gt=0)
    text: str | None = Field(None, max_length=2000)
    user_id: int | None = None  # berilsa — aynan shu foydalanuvchiga yoziladi


@router.post("/incoming")
async def add_incoming(body: ManualIncomingIn, admin: AdminUser, session: SessionDep):
    """Admin bank xabarini qo'lda kiritadi (yoki summani yozadi)."""
    amount = body.amount or (p2p.parse_bank_message(body.text) if body.text else None)
    if not amount:
        raise AppError("bad_amount", "Matndan kirim summasi topilmadi — summani qo'lda kiriting")
    if amount > 50_000_000:
        raise AppError("bad_amount", "Summa juda katta")
    out = Outbox()
    if body.user_id:
        async with session.begin():
            t = await p2p.credit_to_user(session, body.user_id, amount, body.text, admin.id, out)
        await out.flush()
        return {"id": t.incoming_id, "amount": amount, "status": "matched", "user_id": body.user_id}
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


class ToUserIn(BaseModel):
    user_id: int


@router.post("/incoming/{incoming_id}/to-user")
async def incoming_to_user(incoming_id: int, body: ToUserIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        t = await p2p.credit_to_user(session, body.user_id, 0, None, admin.id, out, incoming_id=incoming_id)
    await out.flush()
    return {"ok": True, "amount": t.pay_amount}


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


@router.post("/donate/{order_id:int}")
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
        digits = "".join(ch for ch in q if ch.isdigit())
        if len(digits) == 8:  # hamyon ID: «VX 1234 5678» yoki «12345678»
            conds.append(User.wallet_id == digits)
        if q.isdigit():
            conds.append(User.id == int(q))
        stmt = stmt.where(or_(*conds))
    return [{**S.user_private(u), "is_banned": u.is_banned, "created_at": S.iso(u.created_at),
             "wallet_id": wallet.format_wallet_id(u.wallet_id)} for u in await session.scalars(stmt)]


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
    game: str = Field(min_length=1, max_length=64)
    name: str = Field(max_length=128)
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
        if p.source == "api":
            p.admin_off = not body.is_active  # sinxronlash admin yashirganini qayta yoqmasin
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
    status: str = Field("open", pattern="^(soon|open|running|finished)$")


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
    value: int | str


@router.put("/settings")
async def put_setting(body: SettingIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        await app_settings.set_value(session, body.key, body.value)
    return await app_settings.get_all(session)


# ------------------------------------------------------------------ bank botlari (Telegram, telefonsiz)
class TgApiIn(BaseModel):
    api_id: str = Field(max_length=20)
    api_hash: str = Field(max_length=64)


class TgPhoneIn(BaseModel):
    phone: str = Field(max_length=20)


class TgCodeIn(BaseModel):
    code: str | None = Field(None, max_length=10)
    password: str | None = Field(None, max_length=200)


class TgBotsIn(BaseModel):
    bots: list[str] = Field(max_length=10)


@router.get("/tg-bank")
async def tg_bank_status(admin: AdminUser):
    from app.services import tg_bank

    return await tg_bank.status()


@router.post("/tg-bank/api")
async def tg_bank_api(body: TgApiIn, admin: AdminUser):
    from app.services import tg_bank

    await tg_bank.save_api(body.api_id, body.api_hash)
    return await tg_bank.status()


@router.post("/tg-bank/code")
async def tg_bank_code(body: TgPhoneIn, admin: AdminUser):
    from app.services import tg_bank

    await rate_limit(f"tgcode:{admin.id}", limit=5, window=3600)
    await tg_bank.send_code(body.phone)
    return await tg_bank.status()


@router.post("/tg-bank/login")
async def tg_bank_login(body: TgCodeIn, admin: AdminUser):
    from app.services import tg_bank

    await rate_limit(f"tglogin:{admin.id}", limit=10, window=3600)
    r = await tg_bank.sign_in(body.code, body.password)
    return {**await tg_bank.status(), **r}


@router.post("/tg-bank/logout")
async def tg_bank_logout(admin: AdminUser):
    from app.services import tg_bank

    await tg_bank.logout()
    return await tg_bank.status()


@router.put("/tg-bank/bots")
async def tg_bank_bots(body: TgBotsIn, admin: AdminUser):
    from app.services import tg_bank

    await tg_bank.set_bots(body.bots)
    return await tg_bank.status()


# ------------------------------------------------------------------ donat API ulanishi
@router.get("/donate/provider")
async def donate_provider_info(admin: AdminUser):
    from urllib.parse import urlparse

    raw = settings.donate_provider
    mode = raw if raw in ("manual", "yupay", "http", "mock") else "noto'g'ri"  # qiymatni hech qachon ko'rsatmaymiz (kalit adashib yozilgan bo'lishi mumkin)
    url = settings.donate_provider_url
    live = mode in ("yupay", "http") and bool(settings.donate_provider_key) and (mode == "yupay" or bool(url))
    base = settings.webapp_url.rstrip("/")
    return {
        "mode": mode, "live": live, "yupay": mode == "yupay", "mode_invalid": raw not in ("manual", "yupay", "http", "mock"),
        "url_set": bool(url) or mode == "yupay", "host": (urlparse(url).netloc if url else "api.yupay.uz") if live else None,
        "key_set": bool(settings.donate_provider_key),
        "webhook_url": f"{base}/api/yupay/webhook", "low_balance_usd": settings.donate_low_balance_usd,
        "auth_header": settings.donate_auth_header, "paths": {"check": settings.donate_check_path, "create": settings.donate_create_path,
                                                              "status": settings.donate_status_path, "balance": settings.donate_balance_path},
    }


@router.post("/donate/provider/test")
async def donate_provider_test(admin: AdminUser):
    from app.providers import get_provider

    p = get_provider()
    if not hasattr(p, "ping"):
        return {"ok": False, "error": "Provayder ulanmagan: Render'da DONATE_PROVIDER=yupay va DONATE_PROVIDER_KEY qo'yilmagan"}
    return await p.ping()


@router.get("/donate/yupay/skus")
async def yupay_skus(admin: AdminUser, session: SessionDep, game: str = "ML"):
    """Paket SKU'sini tanlash uchun Yupay katalogi (faqat tanlangan o'yin brendlari)."""
    from app.providers import get_provider
    from app.services import donate_catalog

    p = get_provider()
    if not hasattr(p, "skus_for"):  # Render'dagi sozlama yo'q — admin paneldan qo'shilgan birinchi Yupay API
        row = await session.scalar(select(DonateProvider).where(DonateProvider.kind == "yupay", DonateProvider.is_active.is_(True)).order_by(DonateProvider.id).limit(1))
        if row is None:
            raise BadState("Yupay ulanmagan")
        p = donate_catalog.provider_instance(row)
    try:
        return await p.skus_for(game)
    except Exception as e:  # noqa: BLE001
        raise AppError("yupay_catalog", f"Katalogni olib bo'lmadi: {e.__class__.__name__}", 502) from None


# ------------------------------------------------------------------ foydalanuvchi kartochkasi
@router.get("/users/{user_id}/card")
async def user_card(user_id: int, admin: AdminUser, session: SessionDep):
    from app.models import AdminLog, LedgerEntry, Rental

    u = await session.get(User, user_id)
    if u is None:
        raise NotFound("Foydalanuvchi")

    async def agg(model, amount_col, *where):
        row = (await session.execute(select(func.count(), func.coalesce(func.sum(amount_col), 0)).where(*where))).one()
        return {"count": int(row[0]), "sum": int(row[1])}

    stats = {
        "topups": await agg(Topup, Topup.pay_amount, Topup.user_id == u.id, Topup.status == "paid"),
        "purchases": await agg(Deal, Deal.price, Deal.buyer_id == u.id, Deal.status == "completed"),
        "sales": await agg(Deal, Deal.price, Deal.seller_id == u.id, Deal.status == "completed"),
        "donates": await agg(DonateOrder, DonateOrder.price, DonateOrder.user_id == u.id, DonateOrder.status == "done"),
        "tg": await agg(TgOrder, TgOrder.price, TgOrder.user_id == u.id, TgOrder.status == "done"),
        "boosts": await agg(BoostOrder, BoostOrder.price, BoostOrder.user_id == u.id),
        "rentals": await agg(Rental, Rental.price, or_(Rental.renter_id == u.id, Rental.owner_id == u.id)),
        "withdrawals": await agg(Withdrawal, Withdrawal.amount, Withdrawal.user_id == u.id, Withdrawal.status == "paid"),
        "disputes": {"count": int(await session.scalar(select(func.count()).select_from(Deal).where(
            or_(Deal.buyer_id == u.id, Deal.seller_id == u.id), Deal.dispute_reason.is_not(None))) or 0), "sum": 0},
        "listings": {"count": int(await session.scalar(select(func.count()).select_from(Listing).where(Listing.seller_id == u.id)) or 0), "sum": 0},
        "invited": {"count": int(await session.scalar(select(func.count()).select_from(User).where(User.referrer_id == u.id)) or 0), "sum": 0},
    }
    ledger = list(await session.scalars(select(LedgerEntry).where(LedgerEntry.user_id == u.id).order_by(LedgerEntry.id.desc()).limit(40)))
    logs = list(await session.scalars(select(AdminLog).where(AdminLog.target_user == u.id).order_by(AdminLog.id.desc()).limit(20)))
    return {
        "user": {**S.user_private(u), "is_banned": u.is_banned, "created_at": S.iso(u.created_at), "last_seen_at": S.iso(u.last_seen_at),
                 "wallet_id": wallet.format_wallet_id(u.wallet_id), "kyc_status": u.kyc_status, "referrer_id": u.referrer_id,
                 "withdrawable": (await wallet.withdrawable(session, u.id, u.balance))["available"]},
        "stats": stats,
        "ledger": [{"id": e.id, "amount": e.amount, "balance_after": e.balance_after, "kind": e.kind, "note": e.note,
                    "created_at": S.iso(e.created_at)} for e in ledger],
        "admin_log": [_log_dict(x) for x in logs],
    }


def _log_dict(x) -> dict:
    return {"id": x.id, "admin_id": x.admin_id, "action": x.action, "summary": x.summary, "amount": x.amount,
            "target_user": x.target_user, "created_at": S.iso(x.created_at)}


# ------------------------------------------------------------------ admin jurnali
@router.get("/audit")
async def audit_log(admin: AdminUser, session: SessionDep, before: int = 0, user: int = 0):
    from app.models import AdminLog

    q = select(AdminLog).order_by(AdminLog.id.desc()).limit(50)
    if before:
        q = q.where(AdminLog.id < before)
    if user:
        q = q.where(AdminLog.target_user == user)
    rows = list(await session.scalars(q))
    names = {u.id: (f"@{u.username}" if u.username else u.first_name) for u in await session.scalars(
        select(User).where(User.id.in_({r.admin_id for r in rows} | {r.target_user for r in rows if r.target_user} or {0})))}
    return [{**_log_dict(r), "admin_name": names.get(r.admin_id, str(r.admin_id)),
             "target_name": names.get(r.target_user) if r.target_user else None} for r in rows]


# ------------------------------------------------------------------ grafik / hisobot
@router.get("/analytics")
async def analytics(admin: AdminUser, session: SessionDep, days: int = 30):
    from app.services import reports

    return await reports.analytics(session, days)


@router.post("/report/send")
async def report_now(admin: AdminUser, session: SessionDep):
    """Hisobotni hozir guruhga yuborish (sinash uchun)."""
    from app.services import reports

    text = await reports.daily_text(session)
    out = Outbox()
    out.admins(text, topic="hisobot")
    await out.flush()
    return {"ok": True, "text": text}


# ------------------------------------------------------------------ promo-kodlar
class PromoIn(BaseModel):
    code: str = Field(min_length=3, max_length=32)
    amount: int = Field(gt=0, le=5_000_000)
    max_uses: int = Field(100, ge=1, le=100_000)
    days: int = Field(30, ge=0, le=365)  # 0 — muddatsiz
    need_topup: bool = True


@router.get("/promo")
async def promo_list(admin: AdminUser, session: SessionDep):
    from app.models import PromoCode
    from app.services.promo import promo_dict

    return [promo_dict(p) for p in await session.scalars(select(PromoCode).order_by(PromoCode.id.desc()).limit(100))]


@router.post("/promo")
async def promo_create(body: PromoIn, admin: AdminUser, session: SessionDep):
    from app.models import PromoCode
    from app.services.promo import clean_code, promo_dict

    code = clean_code(body.code)
    if len(code) < 3:
        raise AppError("bad_promo", "Kod faqat lotin harf va raqamlardan iborat bo'lsin")
    async with session.begin():
        if await session.scalar(select(PromoCode.id).where(PromoCode.code == code)):
            raise BadState("Bunday kod bor")
        p = PromoCode(code=code, amount=body.amount, max_uses=body.max_uses, need_topup=body.need_topup, created_by=admin.id,
                      expires_at=datetime.now(timezone.utc) + timedelta(days=body.days) if body.days else None)
        session.add(p)
    return promo_dict(p)


@router.post("/promo/{pid}/toggle")
async def promo_toggle(pid: int, admin: AdminUser, session: SessionDep):
    from app.models import PromoCode
    from app.services.promo import promo_dict

    async with session.begin():
        p = await session.get(PromoCode, pid)
        if p is None:
            raise NotFound("Promo-kod")
        p.active = not p.active
    return promo_dict(p)


# ------------------------------------------------------------------ ommaviy xabar
class BroadcastIn(BaseModel):
    text: str = Field(min_length=2, max_length=3500)
    audience: str = Field("all", pattern="^(all|active7|buyers|sellers|verified|no_topup)$")
    button: bool = True
    test: bool = False


AUDIENCES = {"all": "Hammaga", "active7": "Oxirgi 7 kunda kirganlar", "buyers": "Xarid qilganlar",
             "sellers": "Sotuvchilar", "verified": "Tasdiqlanganlar (KYC)", "no_topup": "Hali to'ldirmaganlar"}
_broadcast: dict = {"running": False, "sent": 0, "failed": 0, "total": 0, "audience": None, "started_at": None}


def _audience_query(aud: str):
    from app.api.user import SPEND_KINDS
    from app.models import LedgerEntry, RentListing

    q = select(User.id).where(User.is_banned.is_(False))
    if aud == "active7":
        q = q.where(User.last_seen_at >= datetime.now(timezone.utc) - timedelta(days=7))
    elif aud == "buyers":
        q = q.where(User.id.in_(select(LedgerEntry.user_id).where(LedgerEntry.kind.in_(SPEND_KINDS))))
    elif aud == "sellers":
        q = q.where(or_(User.id.in_(select(Listing.seller_id)), User.id.in_(select(RentListing.owner_id))))
    elif aud == "verified":
        q = q.where(User.kyc_status == "verified")
    elif aud == "no_topup":
        q = q.where(User.id.not_in(select(Topup.user_id).where(Topup.status == "paid")))
    return q


@router.get("/broadcast")
async def broadcast_status(admin: AdminUser, session: SessionDep):
    counts = {k: int(await session.scalar(select(func.count()).select_from(_audience_query(k).subquery())) or 0) for k in AUDIENCES}
    return {**{k: v for k, v in _broadcast.items() if k != "task"}, "audiences": [{"v": k, "label": v, "count": counts[k]} for k, v in AUDIENCES.items()]}


@router.post("/broadcast")
async def broadcast(body: BroadcastIn, admin: AdminUser, session: SessionDep):
    import asyncio

    from app.services.notify import webapp_button

    markup = webapp_button("🎮 VAYNEXO ni ochish") if body.button else None
    out = Outbox()
    if body.test:
        out.user(admin.id, body.text, markup)
        await out.flush()
        return {"ok": True, "test": True}
    if _broadcast["running"]:
        raise BadState("Oldingi xabar hali yuborilmoqda")
    ids = list(await session.scalars(_audience_query(body.audience)))
    _broadcast.update(running=True, sent=0, failed=0, total=len(ids), audience=AUDIENCES[body.audience],
                      started_at=datetime.now(timezone.utc).isoformat())

    async def run() -> None:
        from app.services import notify

        try:
            for uid in ids:
                try:
                    await notify._sender(uid, body.text, markup)
                    _broadcast["sent"] += 1
                except Exception:  # noqa: BLE001
                    _broadcast["failed"] += 1
                await asyncio.sleep(0.05)  # Telegram limiti: ~20 xabar/soniya
        finally:
            _broadcast["running"] = False

    _broadcast["task"] = asyncio.create_task(run())
    return {k: v for k, v in _broadcast.items() if k != "task"}


# ------------------------------------------------------------------ donat provayderlari (bir nechta API)
KINDS = {"yupay": "Yupay Merchant API", "http": "Umumiy HTTP API (qo'lda paketlar)"}


class ProviderIn(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    kind: str = Field("yupay", pattern="^(yupay|http)$")
    base_url: str = Field("", max_length=200)
    api_key: str | None = Field(None, max_length=300)  # bo'sh/None — eski kalit saqlanadi
    is_active: bool = True
    config: dict | None = None


def _provider_dict(p: DonateProvider) -> dict:
    from urllib.parse import urlparse

    return {"id": p.id, "name": p.name, "kind": p.kind, "kind_label": KINDS.get(p.kind, p.kind),
            "base_url": p.base_url, "host": urlparse(p.base_url).netloc if p.base_url else ("api.yupay.uz" if p.kind == "yupay" else None),
            "key_set": bool(p.key_enc), "is_active": p.is_active, "config": p.config or {},
            "last_ok_at": S.iso(p.last_ok_at), "last_error": p.last_error, "synced_at": S.iso(p.synced_at),
            "balance_usd": p.balance_usd,
            "webhook_url": f"{settings.webapp_url.rstrip('/')}/api/yupay/webhook/{p.id}" if p.kind == "yupay" else None}


@router.get("/donate/providers")
async def donate_providers(admin: AdminUser, session: SessionDep):
    rows = list(await session.scalars(select(DonateProvider).order_by(DonateProvider.id)))
    legacy = settings.donate_provider in ("yupay", "http") and bool(settings.donate_provider_key)
    return {"providers": [_provider_dict(p) for p in rows], "legacy_env": legacy,
            "usd_rate": int(await app_settings.get_value(session, "donate_usd_rate")),
            "markup": int(await app_settings.get_value(session, "donate_markup_percent"))}


@router.post("/donate/providers")
async def donate_provider_create(body: ProviderIn, admin: AdminUser, session: SessionDep):
    from app.security import encrypt

    key = (body.api_key or "").strip()
    if not key:
        raise AppError("no_key", "API kalitni kiriting")
    if body.kind == "http" and not body.base_url.startswith("https://"):
        raise AppError("bad_url", "Manzil https:// bilan boshlansin")
    async with session.begin():
        p = DonateProvider(name=body.name.strip(), kind=body.kind, base_url="" if body.kind == "yupay" and "/merchant/" not in body.base_url else body.base_url.strip(), key_enc=encrypt(key),
                           is_active=body.is_active, config=body.config or {})
        session.add(p)
    # Qo'shilishi bilan katalog avtomatik yuklanadi (xato bo'lsa provayder saqlanib qoladi, xatosi ko'rsatiladi)
    pid, active = p.id, p.is_active
    if active:
        from app.services import donate_catalog

        try:
            async with session.begin():
                await donate_catalog.sync_provider(session, await session.get(DonateProvider, pid))
        except Exception as e:  # noqa: BLE001
            err = f"{e.__class__.__name__}: {str(e)[:200]}"
            async with session.begin():
                (await session.get(DonateProvider, pid)).last_error = err
        await invalidate_packages_cache()
        async with session.begin():
            return _provider_dict(await session.get(DonateProvider, pid, populate_existing=True))
    return _provider_dict(p)


@router.put("/donate/providers/{pid}")
async def donate_provider_update(pid: int, body: ProviderIn, admin: AdminUser, session: SessionDep):
    from app.security import encrypt
    from app.services import donate_catalog

    async with session.begin():
        p = await session.get(DonateProvider, pid)
        if p is None:
            raise NotFound("Provayder")
        p.name, p.base_url, p.is_active = body.name.strip(), ("" if body.kind == "yupay" and "/merchant/" not in body.base_url else body.base_url.strip()), body.is_active
        if body.config is not None:
            p.config = body.config
        if (body.api_key or "").strip():
            p.key_enc = encrypt(body.api_key.strip())
    donate_catalog.forget_provider(pid)
    return _provider_dict(p)


@router.delete("/donate/providers/{pid}")
async def donate_provider_delete(pid: int, admin: AdminUser, session: SessionDep):
    from app.services import donate_catalog

    async with session.begin():
        p = await session.get(DonateProvider, pid)
        if p is None:
            raise NotFound("Provayder")
        busy = await session.scalar(select(func.count()).select_from(DonateOrder).where(
            DonateOrder.status == "processing", DonateOrder.package_id.in_(select(DonatePackage.id).where(DonatePackage.provider_id == pid))))
        if busy:
            raise BadState("Bu API orqali bajarilayotgan buyurtmalar bor — tugagach o'chiring")
        await session.execute(update(DonatePackage).where(DonatePackage.provider_id == pid, DonatePackage.source == "api").values(is_active=False))
        await session.delete(p)
    donate_catalog.forget_provider(pid)
    await invalidate_packages_cache()
    return {"ok": True}


@router.post("/donate/providers/{pid}/test")
async def donate_provider_test_one(pid: int, admin: AdminUser, session: SessionDep):
    from app.services import donate_catalog

    p = await session.get(DonateProvider, pid)
    if p is None:
        raise NotFound("Provayder")
    inst = donate_catalog.provider_instance(p)
    res = await inst.ping()
    async with session.begin():
        row = await session.get(DonateProvider, pid)
        row.balance_usd = str(res.get("balance_usd")) if res.get("ok") and res.get("balance_usd") is not None else row.balance_usd
        if res.get("ok"):
            row.last_ok_at, row.last_error = datetime.now(timezone.utc), None
        else:
            row.last_error = str(res.get("error"))[:300]
    return res


@router.post("/donate/providers/{pid}/sync")
async def donate_provider_sync(pid: int, admin: AdminUser, session: SessionDep):
    from app.services import donate_catalog

    p = await session.get(DonateProvider, pid)
    if p is None:
        raise NotFound("Provayder")
    await session.rollback()
    try:
        async with SessionLocal() as s, s.begin():
            row = await s.get(DonateProvider, pid)
            stats = await donate_catalog.sync_provider(s, row)
    except Exception as e:  # noqa: BLE001
        async with SessionLocal() as s, s.begin():
            row = await s.get(DonateProvider, pid)
            row.last_error = f"{e.__class__.__name__}: {str(e)[:200]}"
        raise AppError("sync_failed", f"Katalogni olib bo'lmadi: {e.__class__.__name__}. Kalit va manzilni tekshiring", 502) from None
    await invalidate_packages_cache()
    return stats


@router.post("/donate/reprice")
async def donate_reprice(admin: AdminUser, session: SessionDep):
    """Dollar kursi yoki ustama o'zgargach — so'm narxlarni qayta hisoblash (API'siz)."""
    from app.services import donate_catalog

    async with session.begin():
        n = await donate_catalog.reprice(session)
    await invalidate_packages_cache()
    return {"changed": n}


# ------------------------------------------------------------------ o'yinlar (bosh sahifa)
class GameIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    is_active: bool | None = None
    featured_slot: int | None = Field(None, ge=0, le=3)  # 0 — katta kartadan olish
    popular: bool | None = None
    sort: int | None = Field(None, ge=0, le=10_000)


def _game_admin(g: DonateGame, n_pk: int) -> dict:
    logo = f"/api/donate/game-image/{g.slug}?v={g.image_ver}" if g.image_ver else g.logo_url
    return {"slug": g.slug, "name": g.name, "logo": logo, "has_image": bool(g.image_ver), "category": g.category, "is_active": g.is_active,
            "featured_slot": g.featured_slot, "popular": g.popular, "sort": g.sort, "provider_id": g.provider_id,
            "packages": n_pk, "synced_at": S.iso(g.synced_at)}


@router.get("/donate/games")
async def donate_games_admin(admin: AdminUser, session: SessionDep):
    counts = dict((await session.execute(select(DonatePackage.game, func.count()).where(DonatePackage.is_active.is_(True)).group_by(DonatePackage.game))).all())
    rows = await session.scalars(select(DonateGame).order_by(DonateGame.is_active.desc(), DonateGame.sort, DonateGame.name))
    return [_game_admin(g, counts.get(g.slug, 0)) for g in rows]


@router.put("/donate/games/{slug}")
async def donate_game_update(slug: str, body: GameIn, admin: AdminUser, session: SessionDep):
    async with session.begin():
        g = await session.get(DonateGame, slug)
        if g is None:
            raise NotFound("O'yin")
        data = body.model_dump(exclude_unset=True)
        if "featured_slot" in data:
            slot = data.pop("featured_slot") or None
            if slot:  # bitta joyda bitta o'yin
                await session.execute(update(DonateGame).where(DonateGame.featured_slot == slot, DonateGame.slug != slug).values(featured_slot=None))
            g.featured_slot = slot
            if slot:
                g.popular = False
        for k, v in data.items():
            setattr(g, k, v)
        if g.featured_slot and not g.is_active:
            g.featured_slot = None
    await invalidate_packages_cache()
    return _game_admin(g, 0)


@router.post("/donate/games/{slug}/image")
async def donate_game_image(slug: str, file: UploadFile, admin: AdminUser, session: SessionDep):
    """O'yin rasmini yuklash (kvadrat qilib kesiladi, 256×256 WEBP, bazada saqlanadi)."""
    import io

    from PIL import Image, ImageOps
    from starlette.concurrency import run_in_threadpool

    from app.api.media import IMAGE_MAX, _read_limited

    if not (file.content_type or "").startswith("image/"):
        raise AppError("bad_type", "Faqat rasm")
    raw = await _read_limited(file, IMAGE_MAX)

    def square(data: bytes) -> bytes:
        try:
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGBA")
            img = ImageOps.fit(img, (256, 256), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "WEBP", quality=86, method=4)
            return buf.getvalue()
        except Exception as e:  # noqa: BLE001
            raise AppError("bad_image", "Rasmni o'qib bo'lmadi") from e

    data = await run_in_threadpool(square, raw)
    async with session.begin():
        g = await session.get(DonateGame, slug)
        if g is None:
            raise NotFound("O'yin")
        g.image, g.image_ver = data, (g.image_ver or 0) + 1
    await invalidate_packages_cache()
    return {"logo": f"/api/donate/game-image/{slug}?v={g.image_ver}"}


@router.delete("/donate/games/{slug}/image")
async def donate_game_image_delete(slug: str, admin: AdminUser, session: SessionDep):
    async with session.begin():
        g = await session.get(DonateGame, slug)
        if g is None:
            raise NotFound("O'yin")
        g.image, g.image_ver = None, 0
    return {"ok": True}


@router.post("/web-link")
async def web_link(admin: AdminUser):
    """Admin panelni kompyuter brauzerida ochish uchun 12 soatlik havola (token URL fragmentida — serverga yozilmaydi)."""
    from app.security import WEB_TOKEN_TTL, make_web_token

    token = make_web_token(admin.id)
    return {"url": f"{settings.webapp_url.rstrip('/')}/admin?web=1#wt={token}", "ttl_hours": WEB_TOKEN_TTL // 3600}
