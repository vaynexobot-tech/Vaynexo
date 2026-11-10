"""Telegram xabarlari navbat (arq/Redis) orqali yuboriladi — API so'rovi kutib qolmaydi.

Xabar tranzaksiya commit bo'lgandan keyin yuborilishi kerak, shuning uchun
servislar `Outbox` ga yig'adi, API esa commitdan so'ng `flush()` chaqiradi.
"""

import logging
from collections.abc import Awaitable, Callable

from app.config import settings

log = logging.getLogger(__name__)

Sender = Callable[[int, str, dict | None], Awaitable[None]]


async def _enqueue(chat_id: int, text: str, markup: dict | None) -> None:
    from app.queue import enqueue

    try:
        await enqueue("send_tg", chat_id, text, markup)
    except Exception:  # Redis ishlamasa ham asosiy amal buzilmasin
        log.exception("Xabarni navbatga qo'yib bo'lmadi chat_id=%s", chat_id)


_sender: Sender = _enqueue


def set_sender(sender: Sender) -> None:
    """Testlarda xabarlarni ushlab olish uchun."""
    global _sender
    _sender = sender


def webapp_button(text: str, path: str = "") -> dict:
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": settings.webapp_url.rstrip("/") + path}}]]}


# O'chirib qo'yish mumkin bo'lgan xabar turlari -> users jadvalidagi ustun
OPTIONAL_KINDS = {"chat": "notify_chat", "tour": "notify_tour"}


async def _muted(pairs: set[tuple[int, str]]) -> set[tuple[int, str]]:
    """Foydalanuvchi o'chirib qo'ygan ixtiyoriy xabarlar."""
    if not pairs:
        return set()
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User

    try:
        async with SessionLocal() as s:
            rows = (await s.execute(
                select(User.id, User.notify_chat, User.notify_tour).where(User.id.in_({uid for uid, _ in pairs}))
            )).all()
    except Exception:  # baza ishlamasa — yuboraveramiz
        log.exception("Bildirishnoma sozlamalarini o'qib bo'lmadi")
        return set()
    prefs = {r.id: {"notify_chat": r.notify_chat, "notify_tour": r.notify_tour} for r in rows}
    return {(uid, k) for uid, k in pairs if prefs.get(uid, {}).get(OPTIONAL_KINDS[k], True) is False}


class Outbox:
    def __init__(self) -> None:
        self.items: list[tuple[int, str, dict | None]] = []
        self.kinds: dict[int, str] = {}  # items indeksi -> ixtiyoriy tur

    def user(self, chat_id: int, text: str, markup: dict | None = None, kind: str | None = None) -> None:
        if kind in OPTIONAL_KINDS:
            self.kinds[len(self.items)] = kind
        self.items.append((chat_id, text, markup))

    def admins(self, text: str, markup: dict | None = None) -> None:
        if settings.admin_chat_id:
            self.items.append((settings.admin_chat_id, text, markup))
        else:
            for admin_id in settings.admin_ids:
                self.items.append((admin_id, text, markup))

    async def flush(self) -> None:
        items, self.items = self.items, []
        kinds, self.kinds = self.kinds, {}
        muted = await _muted({(items[i][0], k) for i, k in kinds.items()}) if kinds else set()
        for i, (chat_id, text, markup) in enumerate(items):
            if i in kinds and (chat_id, kinds[i]) in muted:
                continue
            await _sender(chat_id, text, markup)


def fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"
