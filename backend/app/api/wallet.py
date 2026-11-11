from typing import Annotated

import logging

from fastapi import APIRouter, Header, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api import schemas as S
from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.api.media import IMAGE_MAX, _read_limited
from app.config import settings
from app.errors import AppError, NotFound
from app.models import LedgerEntry, PaymentCard, Topup, User, Withdrawal
from app.security import decrypt
from app.services import app_settings
from app.services import p2p
from app.services.notify import Outbox
from app.services.services import create_withdrawal

log = logging.getLogger(__name__)
router = APIRouter(prefix="/wallet", tags=["wallet"])


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


@router.get("/topup/{topup_id}")
async def get_topup(topup_id: int, user: CurrentUser, session: SessionDep):
    t = await session.get(Topup, topup_id)
    if t is None or t.user_id != user.id:
        raise NotFound("To'lov so'rovi")
    balance = await session.scalar(select(User.balance).where(User.id == user.id))
    return {**(await _topup(session, t)), "balance": balance}


@router.post("/topup/{topup_id}/paid")
async def topup_paid(topup_id: int, user: CurrentUser, session: SessionDep, receipt: UploadFile | None = None):
    """«To'ladim»: so'rov tekshiruvga o'tadi, adminlarga xabar (chek bo'lsa — rasm bilan) boradi."""
    await rate_limit(f"paid:{user.id}", limit=6, window=600)
    image = None
    if receipt is not None:
        if not (receipt.content_type or "").startswith("image/"):
            raise AppError("bad_image", "Chek rasm bo'lishi kerak")
        image = await _read_limited(receipt, IMAGE_MAX)
    async with session.begin():
        was = await session.scalar(select(Topup.status).where(Topup.id == topup_id, Topup.user_id == user.id))
        t = await p2p.claim_paid(session, user.id, topup_id, image is not None)
    if was != "checking" and t.status == "checking":
        await _notify_review(t, user, image)
    return await _topup(session, t)


async def _notify_review(t: Topup, user: User, image: bytes | None) -> None:
    text, markup = p2p.review_text(t, user), p2p.review_markup(t.id)
    if image is not None and settings.bot_token:
        try:
            from aiogram.types import BufferedInputFile

            from app.bot.instance import get_bot

            targets = [settings.admin_chat_id] if settings.admin_chat_id else list(settings.admin_ids)
            for chat_id in targets:
                await get_bot().send_photo(chat_id, BufferedInputFile(image, f"chek_{t.id}.jpg"), caption=text, reply_markup=markup)
            return
        except Exception:
            log.warning("Chek rasmini adminlarga yuborib bo'lmadi", exc_info=True)
    out = Outbox()
    out.admins(text, markup)
    await out.flush()


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
