"""Birgalikda to'laymiz va Orzu ro'yxati.

split — o'yinchi paketni tanlaydi, do'stlar bo'lib to'laydi; yig'ilgach almaz yaratuvchining akkauntiga tushadi.
wish  — «orzu»: yaratuvchi o'zi to'lamaydi, do'stlar sovg'a sifatida ulush qo'shadi.
Har ulush hamyondan darhol yechiladi (platformada saqlanadi). Maqsadga yetsa buyurtma beriladi; muddat (24 soat) tugasa yoki
yaratuvchi bekor qilsa, hamma ulushlar to'liq qaytariladi.
"""

import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError, BadState, Forbidden, NotFound
from app.models import DonateGame, DonatePackage, Split, SplitPart, User
from app.services import app_settings, wallet
from app.services.notify import Outbox, fmt, webapp_button

ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
MAX_OPEN = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(8))


def link(bot_username: str, code: str) -> str | None:
    return f"https://t.me/{bot_username}?start=split_{code}" if bot_username else None


async def enabled(session: AsyncSession) -> bool:
    return await app_settings.get_value(session, "split_on") == "on"


async def create(session: AsyncSession, creator_id: int, mode: str, package_id: int, player_id: str, zone_id: str, message: str) -> Split:
    if not await enabled(session):
        raise BadState("Bo'lim hozircha yopiq")
    if mode not in ("split", "wish"):
        raise AppError("bad_mode", "Noma'lum rejim")
    pkg = await session.get(DonatePackage, package_id)
    if pkg is None or not pkg.is_active:
        raise NotFound("Paket")
    game = await session.get(DonateGame, pkg.game)
    if game is not None and not game.is_active:
        raise NotFound("O'yin")
    if pkg.delivery != "voucher" and not re.fullmatch(r"[0-9A-Za-z_\-]{3,32}", (player_id or "").strip()):
        raise AppError("bad_id", "O'yin ID'sini to'g'ri kiriting")
    open_count = len(list(await session.scalars(select(Split.id).where(Split.creator_id == creator_id, Split.status == "open"))))
    if open_count >= MAX_OPEN:
        raise BadState(f"Bir vaqtda {MAX_OPEN} tadan ko'p ochiq yig'ish bo'lishi mumkin emas")
    hours = int(await app_settings.get_value(session, "split_hours"))
    s = Split(code=_code(), creator_id=creator_id, mode=mode, title=pkg.name[:120], package_id=pkg.id, player_id=(player_id or "").strip()[:64],
              zone_id=(zone_id or "").strip()[:64], target=pkg.price, collected=0, message=(message or "").strip()[:200], status="open",
              expires_at=_now() + timedelta(hours=hours))
    session.add(s)
    await session.flush()
    return s


async def _lock(session: AsyncSession, code: str) -> Split:
    s = await session.scalar(select(Split).where(Split.code == code).with_for_update().execution_options(populate_existing=True))
    if s is None:
        raise NotFound("Sahifa")
    return s


async def contribute(session: AsyncSession, user_id: int, code: str, amount: int, out: Outbox) -> tuple[Split, int | None]:
    """Ulush qo'shadi. Maqsadga yetsa buyurtma yaratiladi (ID qaytadi — navbatga qo'yish uchun)."""
    s = await _lock(session, code)
    if s.status != "open" or s.expires_at <= _now():
        raise BadState("Yig'ish yakunlangan")
    lo = int(await app_settings.get_value(session, "split_min"))
    remaining = s.target - s.collected
    amount = min(int(amount), remaining)
    if amount < min(lo, remaining):
        raise AppError("bad_amount", f"Kamida {fmt(lo)}")
    part = await session.scalar(select(SplitPart).where(SplitPart.split_id == s.id, SplitPart.user_id == user_id).with_for_update())
    if part is None:
        part = SplitPart(split_id=s.id, user_id=user_id, amount=0)
        session.add(part)
        await session.flush()
    await wallet.debit(session, user_id, amount, "split_in", f"split:{s.id}:{user_id}:{part.amount}", ref_type="split", ref_id=s.id)
    part.amount += amount
    s.collected += amount
    donor = await session.get(User, user_id)
    name = (donor.first_name or "Do'st")[:24]
    if user_id != s.creator_id:
        out.user(s.creator_id, f"🤝 {name} «{s.title}» uchun {fmt(amount)} qo'shdi. Yig'ildi: {fmt(s.collected)} / {fmt(s.target)}",
                 webapp_button("Ochish", f"/split/{s.code}"))
    if s.collected >= s.target:
        return s, await _complete(session, s, out)
    return s, None


async def _complete(session: AsyncSession, s: Split, out: Outbox) -> int:
    from app.services import donate

    order = await donate.create_order(session, s.creator_id, s.package_id, s.player_id, s.zone_id, prepaid=True)
    s.status, s.order_id = "done", order.id
    parts = list(await session.scalars(select(SplitPart).where(SplitPart.split_id == s.id, SplitPart.amount > 0)))
    verb = "sovg'a qilindi" if s.mode == "wish" else "to'landi"
    for p in parts:
        out.user(p.user_id, f"✅ «{s.title}» {verb}! Rahmat, ulushingiz: {fmt(p.amount)}.")
    if all(p.user_id != s.creator_id for p in parts):
        out.user(s.creator_id, f"🎁 Do'stlaringiz «{s.title}» ni sizga {verb}! Almaz yetkazilmoqda.", webapp_button("Tarix", "/history"))
    return order.id


async def _refund_all(session: AsyncSession, s: Split, why: str, out: Outbox) -> None:
    parts = list(await session.scalars(select(SplitPart).where(SplitPart.split_id == s.id, SplitPart.amount > 0)))
    for p in parts:
        await wallet.credit(session, p.user_id, p.amount, "split_refund", f"split:{s.id}:{p.user_id}:refund", ref_type="split", ref_id=s.id)
        out.user(p.user_id, f"↩️ «{s.title}» {why}. {fmt(p.amount)} hamyoningizga qaytarildi.")
        p.amount = 0
    s.collected = 0


async def cancel(session: AsyncSession, user_id: int, code: str, out: Outbox) -> Split:
    s = await _lock(session, code)
    if s.creator_id != user_id:
        raise Forbidden()
    if s.status != "open":
        raise BadState("Yig'ish yakunlangan")
    await _refund_all(session, s, "bekor qilindi", out)
    s.status = "cancelled"
    return s


async def tick(sessions: async_sessionmaker, out: Outbox) -> None:
    """Muddati tugagan yig'ishlar: pul hammaga qaytadi."""
    async with sessions() as session:
        ids = list(await session.scalars(select(Split.code).where(Split.status == "open", Split.expires_at <= _now()).limit(100)))
    for code in ids:
        async with sessions() as session:
            async with session.begin():
                s = await _lock(session, code)
                if s.status != "open" or s.expires_at > _now():
                    continue
                await _refund_all(session, s, "muddatida yig'ilmadi", out)
                s.status = "expired"
                out.user(s.creator_id, f"⌛️ «{s.title}» muddatida yig'ilmadi, ulushlar qaytarildi.")


async def view(session: AsyncSession, code: str, me: int, bot_username: str) -> dict:
    s = await session.scalar(select(Split).where(Split.code == code))
    if s is None:
        raise NotFound("Sahifa")
    creator = await session.get(User, s.creator_id)
    parts = list(await session.scalars(select(SplitPart).where(SplitPart.split_id == s.id, SplitPart.amount > 0).order_by(SplitPart.amount.desc())))
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_([p.user_id for p in parts])))} if parts else {}
    mine = next((p.amount for p in parts if p.user_id == me), 0)
    return {"code": s.code, "mode": s.mode, "title": s.title, "message": s.message, "status": s.status, "target": s.target, "collected": s.collected,
            "remaining": max(0, s.target - s.collected), "expires_at": s.expires_at.isoformat(), "order_id": s.order_id if me == s.creator_id else None,
            "creator": {"id": creator.id, "name": (creator.first_name or "Do'st")[:32]}, "mine": mine, "is_creator": me == s.creator_id,
            "parts": [{"name": (users[p.user_id].first_name or "Do'st")[:24] if p.user_id in users else "Do'st", "amount": p.amount} for p in parts],
            "game_id": s.player_id if me == s.creator_id else None,
            "link": link(bot_username, s.code), "min": int(await app_settings.get_value(session, "split_min"))}


async def my(session: AsyncSession, user_id: int) -> dict:
    made = list(await session.scalars(select(Split).where(Split.creator_id == user_id).order_by(Split.id.desc()).limit(30)))
    joined_ids = list(await session.scalars(select(SplitPart.split_id).where(SplitPart.user_id == user_id, SplitPart.amount > 0)))
    joined = list(await session.scalars(select(Split).where(Split.id.in_(joined_ids), Split.creator_id != user_id).order_by(Split.id.desc()).limit(30))) if joined_ids else []
    row = lambda x: {"code": x.code, "mode": x.mode, "title": x.title, "status": x.status, "target": x.target, "collected": x.collected, "expires_at": x.expires_at.isoformat()}  # noqa: E731
    return {"enabled": await enabled(session), "made": [row(x) for x in made], "joined": [row(x) for x in joined]}
