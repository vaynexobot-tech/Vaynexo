"""Hamyon: balansni o'zgartirishning YAGONA yo'li.

Qoidalar:
* foydalanuvchi qatori `FOR UPDATE` bilan bloklanadi — bir vaqtdagi so'rovlar navbat bilan ishlaydi;
* har bir yozuv noyob `idem_key` ga ega — bir xil amal ikki marta bajarilmaydi
  (masalan, to'lov xabari ikki marta kelsa);
* balans hech qachon manfiy bo'lmaydi (bazada CHECK ham bor).

Funksiya commit qilmaydi — chaqiruvchi o'z tranzaksiyasini o'zi yakunlaydi.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InsufficientFunds, NotFound
from app.models import LedgerEntry, User


async def lock_user(session: AsyncSession, user_id: int) -> User:
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    if user is None:
        raise NotFound("Foydalanuvchi")
    return user


async def change_balance(
    session: AsyncSession,
    user_id: int,
    amount: int,
    kind: str,
    idem_key: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
    note: str | None = None,
) -> LedgerEntry | None:
    """Balansni `amount` ga o'zgartiradi. Shu `idem_key` bilan oldin bajarilgan bo'lsa — None."""
    if amount == 0:
        raise ValueError("amount 0 bo'lishi mumkin emas")
    user = await lock_user(session, user_id)
    exists = await session.scalar(select(LedgerEntry.id).where(LedgerEntry.idem_key == idem_key))
    if exists:
        return None
    new_balance = user.balance + amount
    if new_balance < 0:
        raise InsufficientFunds()
    user.balance = new_balance
    entry = LedgerEntry(
        user_id=user_id,
        amount=amount,
        balance_after=new_balance,
        kind=kind,
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
        idem_key=idem_key,
    )
    session.add(entry)
    await session.flush()
    return entry


async def debit(session: AsyncSession, user_id: int, amount: int, kind: str, idem_key: str, **kw):
    if amount <= 0:
        raise ValueError("debit summasi musbat bo'lishi kerak")
    entry = await change_balance(session, user_id, -amount, kind, idem_key, **kw)
    from app.services import arena  # vazifa: «Istalgan xizmatdan foydalanish»

    await arena.on_payment(session, user_id, kind)
    return entry


async def credit(session: AsyncSession, user_id: int, amount: int, kind: str, idem_key: str, **kw):
    if amount <= 0:
        raise ValueError("credit summasi musbat bo'lishi kerak")
    return await change_balance(session, user_id, amount, kind, idem_key, **kw)


async def add_ticket(session: AsyncSession, user_id: int, n: int = 1) -> None:
    """Konkurs bileti (atomik oshirish)."""
    await session.execute(update(User).where(User.id == user_id).values(tickets=User.tickets + n))


# ---------------------------------------------------------------- hamyon ID va yechish mumkin bo'lgan summa
EARN_KINDS = ("deal_payout", "rent_payout", "boost_payout")


def format_wallet_id(w: str | None) -> str | None:
    return f"VX {w[:4]} {w[4:]}" if w else None


async def ensure_wallet_id(session: AsyncSession, user_id: int) -> str:
    """Foydalanuvchiga hamyon ID beradi (bir marta). 8 xonali tasodifiy raqam, takrorlanmaydi."""
    import secrets

    from sqlalchemy import select, update
    from sqlalchemy.exc import IntegrityError

    from app.models import User

    cur = await session.scalar(select(User.wallet_id).where(User.id == user_id))
    if cur:
        return cur
    for _ in range(10):
        w = str(10_000_000 + secrets.randbelow(90_000_000))
        try:
            async with session.begin_nested():
                res = await session.execute(update(User).where(User.id == user_id, User.wallet_id.is_(None)).values(wallet_id=w))
            if res.rowcount:
                return w
            return await session.scalar(select(User.wallet_id).where(User.id == user_id))
        except IntegrityError:
            continue
    raise RuntimeError("hamyon ID berib bo'lmadi")


async def withdrawable(session: AsyncSession, user_id: int, balance: int) -> dict:
    """Yechish faqat ishlab topilgan pul (sotuv, ijara, boost) uchun. To'ldirilgan pul yechilmaydi."""
    from sqlalchemy import func, select

    from app.models import LedgerEntry

    rows = dict((await session.execute(
        select(LedgerEntry.kind, func.coalesce(func.sum(LedgerEntry.amount), 0))
        .where(LedgerEntry.user_id == user_id, LedgerEntry.kind.in_((*EARN_KINDS, "withdraw", "withdraw_refund")))
        .group_by(LedgerEntry.kind)
    )).all())
    earned = sum(int(rows.get(k, 0)) for k in EARN_KINDS)
    withdrawn = -(int(rows.get("withdraw", 0)) + int(rows.get("withdraw_refund", 0)))
    return {"earned": earned, "withdrawn": withdrawn, "available": max(0, min(balance, earned - withdrawn))}
