from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api import schemas as S
from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.config import settings
from app.errors import AppError, NotFound
from app.models import LedgerEntry, Topup, User, Withdrawal
from app.services import p2p
from app.services.notify import Outbox
from app.services.services import create_withdrawal

router = APIRouter(prefix="/wallet", tags=["wallet"])


def _topup(t: Topup) -> dict:
    return S.topup(t, settings.p2p_card_number, settings.p2p_card_holder)


@router.get("")
async def wallet_info(user: CurrentUser, session: SessionDep, offset: int = 0):
    entries = await session.scalars(
        select(LedgerEntry).where(LedgerEntry.user_id == user.id).order_by(LedgerEntry.id.desc()).offset(max(0, offset)).limit(30)
    )
    pending = await session.scalar(
        select(Topup).where(Topup.user_id == user.id, Topup.status == "pending").order_by(Topup.id.desc()).limit(1)
    )
    return {
        "balance": user.balance,
        "entries": [S.ledger(e) for e in entries],
        "pending_topup": _topup(pending) if pending else None,
        "limits": {"topup_min": settings.topup_min, "topup_max": settings.topup_max, "withdraw_min": settings.withdraw_min,
                   "ttl_minutes": settings.topup_ttl_minutes},
    }


class TopupIn(BaseModel):
    amount: int = Field(gt=0)


@router.post("/topup")
async def create_topup(body: TopupIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"topup:{user.id}", limit=5, window=60)
    async with session.begin():
        t = await p2p.create_topup(session, user.id, body.amount)
    return _topup(t)


@router.get("/topup/{topup_id}")
async def get_topup(topup_id: int, user: CurrentUser, session: SessionDep):
    t = await session.get(Topup, topup_id)
    if t is None or t.user_id != user.id:
        raise NotFound("To'lov so'rovi")
    balance = await session.scalar(select(User.balance).where(User.id == user.id))
    return {**_topup(t), "balance": balance}


@router.post("/topup/{topup_id}/cancel")
async def cancel_topup(topup_id: int, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await p2p.cancel_topup(session, user.id, topup_id)
    return {"ok": True}


class WithdrawIn(BaseModel):
    amount: int = Field(gt=0)
    card_number: str = Field(max_length=32)
    card_holder: str = Field("", max_length=64)


@router.post("/withdraw")
async def withdraw(body: WithdrawIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        w = await create_withdrawal(session, user.id, body.amount, body.card_number, body.card_holder, out)
    await out.flush()
    return S.withdrawal(w)


@router.get("/withdrawals")
async def withdrawals(user: CurrentUser, session: SessionDep):
    rows = await session.scalars(select(Withdrawal).where(Withdrawal.user_id == user.id).order_by(Withdrawal.id.desc()).limit(30))
    return [S.withdrawal(w) for w in rows]


# ------------------------------------------------------------------ kirim xabarlari (SMS-forwarder)
p2p_router = APIRouter(prefix="/p2p", tags=["p2p"])


class IncomingIn(BaseModel):
    text: str | None = Field(None, max_length=2000)  # SMS / bildirishnoma matni
    amount: int | None = Field(None, gt=0)  # matn bo'lmasa summani to'g'ridan-to'g'ri yuborish mumkin
    external_id: str | None = Field(None, max_length=128)  # SMS id — takrorni oldini olish uchun


@p2p_router.post("/incoming")
async def incoming(body: IncomingIn, session: SessionDep, x_p2p_secret: Annotated[str | None, Header()] = None):
    """Android SMS-forwarder ilovasi (yoki boshqa manba) shu manzilga POST qiladi.

    Sarlavha: X-P2P-Secret: <P2P_SECRET>
    """
    import hmac

    if not x_p2p_secret or not hmac.compare_digest(x_p2p_secret, settings.p2p_secret) or settings.p2p_secret == "change-me":
        raise AppError("unauthorized", "Noto'g'ri kalit", 401)
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
