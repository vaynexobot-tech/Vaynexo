"""Promo-kodlar: hamyonga bir martalik bonus."""

import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import LedgerEntry, PromoCode, PromoRedemption
from app.services import wallet
from app.services.notify import fmt


def clean_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9_-]", "", (code or "").strip().upper())[:32]


async def redeem(session: AsyncSession, user_id: int, code: str) -> int:
    code = clean_code(code)
    if len(code) < 3:
        raise AppError("bad_promo", "Promo-kodni kiriting")
    p = await session.scalar(select(PromoCode).where(PromoCode.code == code).with_for_update())
    now = datetime.now(timezone.utc)
    if p is None or not p.active:
        raise AppError("bad_promo", "Bunday promo-kod yo'q", 404)
    if p.expires_at and p.expires_at < now:
        raise AppError("promo_expired", "Promo-kod muddati tugagan")
    if p.used >= p.max_uses:
        raise AppError("promo_used_up", "Promo-kod limiti tugagan")
    if p.need_topup:
        topped = await session.scalar(select(func.count()).select_from(LedgerEntry)
                                      .where(LedgerEntry.user_id == user_id, LedgerEntry.kind == "topup"))
        if not topped:
            raise AppError("promo_need_topup", "Bu promo-kod hamyonini kamida bir marta to'ldirganlar uchun")
    try:
        async with session.begin_nested():
            session.add(PromoRedemption(promo_id=p.id, user_id=user_id))
    except IntegrityError:
        raise AppError("promo_again", "Siz bu promo-koddan foydalangansiz") from None
    p.used += 1
    await wallet.credit(session, user_id, p.amount, "promo", f"promo:{p.id}:{user_id}", ref_type="promo", ref_id=p.id,
                        note=f"Promo-kod {p.code}")
    return p.amount


def promo_dict(p: PromoCode) -> dict:
    from app.api.schemas import iso

    return {"id": p.id, "code": p.code, "amount": p.amount, "max_uses": p.max_uses, "used": p.used,
            "expires_at": iso(p.expires_at), "need_topup": p.need_topup, "active": p.active, "created_at": iso(p.created_at),
            "label": f"{p.code} · +{fmt(p.amount)}"}
