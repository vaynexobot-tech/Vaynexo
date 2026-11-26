"""Signallar: «Ikki barobar almaz qaytdi» kabi xabarlarga obuna.

- Foydalanuvchi obuna bo'ladi (bir tugma).
- Admin signalni yuboradi → barcha obunachilarga xabar + «Donat» tugmasi.
- Katalog yangilanganda «double / 2x / first top-up» nomli paket paydo bo'lsa, adminga darhol eslatma ketadi
  (yuborish-yubormaslikni admin hal qiladi: noto'g'ri signal ishonchni buzadi).
"""

import re

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import AlertSub, DonatePackage, SignalLog
from app.services.notify import Outbox, webapp_button

KINDS = {"double": "⚡️ Ikki barobar almaz"}
DOUBLE_RE = re.compile(r"double|2x|x2|first\s*(top|recharge)|ikki\s*barobar|двойн", re.I)
DEFAULT_TEXT = ("⚡️ Ikki barobar almaz qaytdi!\n\nMLBB birinchi to'ldirish bonusini yangiladi — hozir olgan almazingiz ikki barobar bo'lib tushadi. "
                "Bonus cheklangan vaqtga.")


def _kind(kind: str) -> str:
    if kind not in KINDS:
        raise AppError("bad_kind", "Noma'lum signal")
    return kind


async def is_on(session: AsyncSession, user_id: int, kind: str) -> bool:
    return bool(await session.get(AlertSub, (user_id, _kind(kind))))


async def set_on(session: AsyncSession, user_id: int, kind: str, on: bool) -> bool:
    _kind(kind)
    cur = await session.get(AlertSub, (user_id, kind))
    if on and cur is None:
        session.add(AlertSub(user_id=user_id, kind=kind))
    elif not on and cur is not None:
        await session.execute(delete(AlertSub).where(AlertSub.user_id == user_id, AlertSub.kind == kind))
    return on


async def count(session: AsyncSession, kind: str) -> int:
    return int(await session.scalar(select(func.count()).select_from(AlertSub).where(AlertSub.kind == _kind(kind))) or 0)


async def broadcast(session: AsyncSession, kind: str, text: str, out: Outbox) -> int:
    _kind(kind)
    text = (text or "").strip()[:1000] or DEFAULT_TEXT
    ids = list(await session.scalars(select(AlertSub.user_id).where(AlertSub.kind == kind)))
    for uid in ids:
        out.user(uid, text, webapp_button("💎 Donat qilish", "/donate/ML"))
    session.add(SignalLog(kind=kind, text=text, sent=len(ids)))
    return len(ids)


async def history(session: AsyncSession, kind: str = "double", limit: int = 10) -> list[dict]:
    rows = await session.scalars(select(SignalLog).where(SignalLog.kind == kind).order_by(SignalLog.id.desc()).limit(limit))
    return [{"id": r.id, "text": r.text, "sent": r.sent, "at": r.created_at.isoformat()} for r in rows]


async def detect(session: AsyncSession, out: Outbox) -> list[int]:
    """Katalogda yangi «double» paketlar paydo bo'lsa — adminga eslatma (bir marta)."""
    rows = list(await session.scalars(select(DonatePackage).where(DonatePackage.game == "ML", DonatePackage.is_active.is_(True))))
    found = sorted(p.id for p in rows if DOUBLE_RE.search(p.name or ""))
    last = await session.scalar(select(SignalLog).where(SignalLog.kind == "detect").order_by(SignalLog.id.desc()).limit(1))
    prev = set((last.payload or {}).get("ids", [])) if last else set()
    new = [i for i in found if i not in prev]
    if set(found) != prev:
        session.add(SignalLog(kind="detect", text="", sent=0, payload={"ids": found}))
    if new:
        names = ", ".join(p.name for p in rows if p.id in new)[:300]
        subs = await count(session, "double")
        out.admins(f"⚡️ Katalogda ikki barobar paket paydo bo'ldi: {names}\n\nObunachilar: {subs}. Signal yuborish: Admin → Ko'proq → Signal.",
                   webapp_button("Signal yuborish", "/admin"), topic="boshqa")
    return new
