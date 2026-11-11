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
