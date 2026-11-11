from typing import Annotated

import logging

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api import schemas as S
from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.config import settings
from app.errors import AppError, NotFound
from app.models import LedgerEntry, PaymentCard, Topup, User, Withdrawal
from app.security import decrypt
from app.services import app_settings
from app.services import wallet as wallet_svc
from app.services import p2p
from app.services.notify import Outbox
from app.services.services import create_withdrawal

log = logging.getLogger(__name__)
router = APIRouter(prefix="/wallet", tags=["wallet"])


async def _wid(session, uid: int) -> str:
    w = await wallet_svc.ensure_wallet_id(session, uid)
    await session.commit()
    return w


async def _topup(session, t: Topup) -> dict:
    cards = await p2p.active_cards(session)
    first = cards[0] if cards else {"number": "", "holder": ""}
    return S.topup(t, first["number"], first["holder"], cards)


@router.get("")
async def wallet_info(user: CurrentUser, session: SessionDep, offset: int = 0):
    entries = await session.scalars(
        select(LedgerEntry).where(LedgerEntry.user_id == user.id).order_by(LedgerEntry.id.desc()).offset(max(0, offset)).limit(30)
    )
    pending = await session.scalar(
        select(Topup).where(Topup.user_id == user.id, Topup.status.in_(("pending", "checking"))).order_by(Topup.id.desc()).limit(1)
    )
    return {
        "balance": user.balance,
        "entries": [S.ledger(e) for e in entries],
        "pending_topup": await _topup(session, pending) if pending else None,
        "limits": {"topup_min": settings.topup_min,
                   "topup_max": min(settings.topup_max, int(await app_settings.get_value(session, "topup_max_silver"))),
                   "withdraw_min": settings.withdraw_min,
                   "ttl_minutes": int(await app_settings.get_value(session, "topup_timeout_minutes"))},
        "level": "Silver",
        "wallet_id": wallet_svc.format_wallet_id(await _wid(session, user.id)),
        "withdraw": await wallet_svc.withdrawable(session, user.id, user.balance),
    }


class TopupIn(BaseModel):
    amount: int = Field(gt=0)


@router.post("/topup")
async def create_topup(body: TopupIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"topup:{user.id}", limit=5, window=60)
    async with session.begin():
        if not await p2p.active_cards(session):
            raise AppError("no_card", "To'lov kartasi sozlanmagan. Birozdan so'ng urinib ko'ring", 503)
        t = await p2p.create_topup(session, user.id, body.amount)
    return await _topup(session, t)


@router.post("/topup/{topup_id}/cancel")
async def cancel_topup(topup_id: int, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await p2p.cancel_topup(session, user.id, topup_id)
    return {"ok": True}


class WithdrawIn(BaseModel):
    amount: int = Field(gt=0)
    card_number: str = Field("", max_length=32)
    card_holder: str = Field("", max_length=64)
    card_id: int | None = None  # saqlangan karta


@router.post("/withdraw")
async def withdraw(body: WithdrawIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    number, holder = body.card_number, body.card_holder
    if body.card_id:
        card = await session.get(PaymentCard, body.card_id)
        if not card or card.user_id != user.id:
            raise AppError("not_found", "Karta topilmadi", 404)
        number, holder = decrypt(card.number_enc) or "", card.holder
        await session.commit()
    async with session.begin():
        w = await create_withdrawal(session, user.id, body.amount, number, holder, out)
    await out.flush()
    return S.withdrawal(w)


@router.get("/withdrawals")
async def withdrawals(user: CurrentUser, session: SessionDep):
    rows = await session.scalars(select(Withdrawal).where(Withdrawal.user_id == user.id).order_by(Withdrawal.id.desc()).limit(30))
    return [S.withdrawal(w) for w in rows]


# ------------------------------------------------------------------ kirim xabarlari (SMS-forwarder)
@router.get("/topup/{topup_id}")
async def get_topup(topup_id: int, user: CurrentUser, session: SessionDep):
    t = await session.get(Topup, topup_id)
    if t is None or t.user_id != user.id:
        raise NotFound("To'lov so'rovi")
    balance = await session.scalar(select(User.balance).where(User.id == user.id))
    return {**(await _topup(session, t)), "balance": balance}


@router.post("/topup/{topup_id}/paid")
async def topup_paid(topup_id: int, user: CurrentUser, session: SessionDep):
    """«To'ladim»: so'rov avtomatik tekshiruvga o'tadi (chek kerak emas)."""
    await rate_limit(f"paid:{user.id}", limit=6, window=600)
    async with session.begin():
        t = await p2p.claim_paid(session, user.id, topup_id)
    return await _topup(session, t)


p2p_router = APIRouter(prefix="/p2p", tags=["p2p"])


async def _incoming_body(request: Request) -> "IncomingIn":
    raw = (await request.body())[:20_000]
    data: dict = {}
    ctype = request.headers.get("content-type", "")
    try:
        if "json" in ctype or raw[:1] in (b"{", b"["):
            import json

            parsed = json.loads(raw or b"{}")
            data = parsed if isinstance(parsed, dict) else {}
        elif "form" in ctype:
            from urllib.parse import parse_qsl

            data = dict(parse_qsl(raw.decode("utf-8", "ignore")))
        else:
            data = {"text": raw.decode("utf-8", "ignore")}
    except ValueError:
        data = {"text": raw.decode("utf-8", "ignore")}
    text = next((str(data[k]) for k in ("text", "message", "msg", "body", "sms", "content") if data.get(k)), None)
    amount = data.get("amount")
    ext = next((str(data[k]) for k in ("external_id", "id", "sentStamp", "receivedStamp", "timestamp") if data.get(k)), None)
    try:
        amount = int(amount) if amount not in (None, "") else None
    except (TypeError, ValueError):
        amount = None
    return IncomingIn(text=(text or None) and text[:2000], amount=amount if amount and amount > 0 else None,
                      external_id=(ext or None) and ext[:128])


class IncomingIn(BaseModel):
    text: str | None = Field(None, max_length=2000)  # SMS / bildirishnoma matni
    amount: int | None = Field(None, gt=0)  # matn bo'lmasa summani to'g'ridan-to'g'ri yuborish mumkin
    external_id: str | None = Field(None, max_length=128)  # SMS id — takrorni oldini olish uchun


@p2p_router.post("/incoming")
async def incoming(request: Request, session: SessionDep, x_p2p_secret: Annotated[str | None, Header()] = None, key: str | None = None):
    """Android SMS-forwarder ilovasi (yoki boshqa manba) shu manzilga POST qiladi.

    Kalit: sarlavha X-P2P-Secret yoki ?key=... (ba'zi ilovalar sarlavha qo'sha olmaydi).
    Tana: JSON {"text": "..."} (yoki message / msg / body / sms), shuningdek oddiy matn yoki forma.
    """
    import hmac

    secret = x_p2p_secret or key
    if not secret or settings.p2p_secret == "change-me" or not hmac.compare_digest(secret, settings.p2p_secret):
        raise AppError("unauthorized", "Noto'g'ri kalit", 401)
    body = await _incoming_body(request)
    amount = body.amount or (p2p.parse_bank_message(body.text) if body.text else None)
    if not amount:
        return {"ok": True, "matched": False, "reason": "kirim emas yoki summa topilmadi"}
    out = Outbox()
    async with session.begin():
        inc = await p2p.register_incoming(session, amount, "sms", out, raw_text=body.text, external_id=body.external_id)
    await out.flush()
    if inc is None:
        return {"ok": True, "duplicate": True}
    return {"ok": True, "incoming_id": inc.id, "amount": amount, "matched": inc.status == "matched"}
