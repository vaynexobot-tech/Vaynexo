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


ADMINS = object()  # Outbox.admins() belgisi
ADMIN_CHAT_KEY = "_admin_chat_id"


async def get_admin_chat() -> int | None:
    """Admin xabarlari yuboriladigan kanal/guruh (/admin_kanal bilan belgilanadi)."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import AppSetting

    try:
        async with SessionLocal() as s:
            v = await s.scalar(select(AppSetting.value).where(AppSetting.key == ADMIN_CHAT_KEY))
        return int(v) if v else (settings.admin_chat_id or None)
    except Exception:  # noqa: BLE001
        log.exception("Admin kanalini o'qib bo'lmadi")
        return settings.admin_chat_id or None


async def set_admin_chat(chat_id: int | None) -> None:
    from sqlalchemy import delete
    from sqlalchemy.dialects.postgresql import insert

    from app.db import SessionLocal
    from app.models import AppSetting

    async with SessionLocal() as s, s.begin():
        if chat_id is None:
            await s.execute(delete(AppSetting).where(AppSetting.key == ADMIN_CHAT_KEY))
        else:
            await s.execute(insert(AppSetting).values(key=ADMIN_CHAT_KEY, value=str(chat_id))
                            .on_conflict_do_update(index_elements=["key"], set_={"value": str(chat_id)}))


def start_param(path: str) -> str:
    """/listing/5 → listing_5 ; /admin?x=1 → admin (t.me/bot?startapp=... uchun)."""
    import re

    p = path.split("?")[0].strip("/").replace("/", "_") or "home"
    return re.sub(r"[^A-Za-z0-9_-]", "", p)[:64] or "home"


def for_group(markup: dict | None) -> dict | None:
    """Kanal/guruhda web_app tugmasi ishlamaydi — t.me/bot?startapp=... havolasiga almashtiriladi."""
    if not markup or "inline_keyboard" not in markup:
        return markup
    base = settings.webapp_url.rstrip("/")
    rows = []
    for row in markup["inline_keyboard"]:
        new = []
        for b in row:
            if "web_app" in b:
                if not settings.bot_username:
                    continue
                path = b["web_app"]["url"][len(base):] if b["web_app"]["url"].startswith(base) else ""
                b = {"text": b["text"], "url": f"https://t.me/{settings.bot_username}?startapp={start_param(path)}"}
            new.append(b)
        if new:
            rows.append(new)
    return {"inline_keyboard": rows} if rows else None


async def _expand_admins(items: list) -> list:
    chat = await get_admin_chat()
    res = []
    for chat_id, text, markup in items:
        if chat_id is not ADMINS:
            res.append((chat_id, text, markup))
        elif chat:
            res.append((chat, text, for_group(markup)))
        else:
            res.extend((a, text, markup) for a in settings.admin_ids)
    return res


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
        self.items.append((ADMINS, text, markup))  # qayerga ketishi flush() da aniqlanadi

    async def flush(self) -> None:
        items, self.items = self.items, []
        kinds, self.kinds = self.kinds, {}
        muted = await _muted({(items[i][0], k) for i, k in kinds.items()}) if kinds else set()
        items = [it for i, it in enumerate(items) if not (i in kinds and (it[0], kinds[i]) in muted)]
        if any(it[0] is ADMINS for it in items):
            items = await _expand_admins(items)
        for chat_id, text, markup in items:
            await _sender(chat_id, text, markup)


def fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"
