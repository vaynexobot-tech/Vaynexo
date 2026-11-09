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
    from app.queue import get_pool

    try:
        pool = await get_pool()
        await pool.enqueue_job("send_tg", chat_id, text, markup)
    except Exception:  # Redis ishlamasa ham asosiy amal buzilmasin
        log.exception("Xabarni navbatga qo'yib bo'lmadi chat_id=%s", chat_id)


_sender: Sender = _enqueue


def set_sender(sender: Sender) -> None:
    """Testlarda xabarlarni ushlab olish uchun."""
    global _sender
    _sender = sender


def webapp_button(text: str, path: str = "") -> dict:
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": settings.webapp_url.rstrip("/") + path}}]]}


class Outbox:
    def __init__(self) -> None:
        self.items: list[tuple[int, str, dict | None]] = []

    def user(self, chat_id: int, text: str, markup: dict | None = None) -> None:
        self.items.append((chat_id, text, markup))

    def admins(self, text: str, markup: dict | None = None) -> None:
        if settings.admin_chat_id:
            self.items.append((settings.admin_chat_id, text, markup))
        else:
            for admin_id in settings.admin_ids:
                self.items.append((admin_id, text, markup))

    async def flush(self) -> None:
        items, self.items = self.items, []
        for chat_id, text, markup in items:
            await _sender(chat_id, text, markup)


def fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"
