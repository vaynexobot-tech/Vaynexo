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


class _Admins:
    """Outbox.admins() belgisi: qaysi mavzuga (topic) tegishli."""

    def __init__(self, topic: str) -> None:
        self.topic = topic


ADMIN_CHAT_KEY = "_admin_chat_id"
TOPIC_KEY = "_topic:"  # + mavzu kaliti → "chat_id:thread_id"
# Guruh mavzulari (Telegram forum topics). Kalit → tavsif. Mavzuda «/mavzu kalit» yoziladi.
TOPICS = {
    "elon": "Akkaunt e'lonlari (moderatsiya)",
    "ijara_elon": "Ijara e'lonlari (moderatsiya)",
    "tolov": "«To'ladim» — tasdiqlanmagan to'lovlar",
    "kirim": "Biriktirilmagan kirimlar (bank)",
    "yechish": "Pul yechish so'rovlari",
    "nizo": "Akkaunt savdosi nizolari",
    "ijara_nizo": "Ijara nizolari",
    "boost_nizo": "Boost nizolari",
    "kyc": "Identifikatsiya so'rovlari",
    "tg": "Telegram xizmatlari (Stars, Premium)",
    "donat": "Donat (almaz) buyurtmalari",
    "boost": "Boost buyurtmalari",
    "hamkor": "Hamkor videolari",
    "yordam": "Yordam so'rovlari",
    "hisobot": "Kunlik hisobot (har kuni 09:00)",
    "boshqa": "Qolgan barcha xabarlar",
    "barcha": "Hamma xabarlarning nusxasi",
}


# Yangi ajratilgan turlar ulanmagan bo'lsa — avvalgi umumiy mavzuga tushadi
FALLBACK = {"ijara_elon": "elon", "ijara_nizo": "nizo", "boost_nizo": "nizo", "kirim": "tolov",
            "tg": "buyurtma", "donat": "buyurtma", "boost": "buyurtma"}


async def get_topics() -> dict[str, tuple[int, int | None]]:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import AppSetting

    try:
        async with SessionLocal() as s:
            rows = (await s.execute(select(AppSetting.key, AppSetting.value).where(AppSetting.key.like(TOPIC_KEY + "%")))).all()
    except Exception:  # noqa: BLE001
        log.exception("Mavzularni o'qib bo'lmadi")
        return {}
    res = {}
    for k, v in rows:
        chat, _, thread = v.partition(":")
        res[k[len(TOPIC_KEY):]] = (int(chat), int(thread) if thread and thread != "0" else None)
    return res


async def set_topic(key: str, chat_id: int | None, thread_id: int | None = None) -> None:
    from sqlalchemy import delete
    from sqlalchemy.dialects.postgresql import insert

    from app.db import SessionLocal
    from app.models import AppSetting

    async with SessionLocal() as s, s.begin():
        if chat_id is None:
            await s.execute(delete(AppSetting).where(AppSetting.key == TOPIC_KEY + key))
        else:
            v = f"{chat_id}:{thread_id or 0}"
            await s.execute(insert(AppSetting).values(key=TOPIC_KEY + key, value=v)
                            .on_conflict_do_update(index_elements=["key"], set_={"value": v}))


def with_thread(markup: dict | None, thread_id: int | None) -> dict | None:
    """Mavzu (thread) raqami markup ichida uzatiladi — send_tg uni ajratib oladi."""
    if not thread_id:
        return markup
    return {**(markup or {}), "_thread": thread_id}


async def admin_targets(topic: str) -> list[tuple[int, int | None]]:
    """Admin xabari qayerlarga ketadi: mavzu → «boshqa» mavzu → admin kanali → shaxsiy. + «barcha» nusxasi."""
    topics = await get_topics()
    main = topics.get(topic) or topics.get(FALLBACK.get(topic, "")) or topics.get("boshqa")
    if not main:
        chat = await get_admin_chat()
        if not chat and topics:
            chat = next(iter(topics.values()))[0]  # mavzular bor guruhning General qismi
        main = (chat, None) if chat else None
    targets = [main] if main else [(a, None) for a in settings.admin_ids]
    if (copy := topics.get("barcha")) and copy not in targets:
        targets.append(copy)
    return targets


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
                # ?start= — bot o'zi «Ochish» tugmasini yuboradi (BotFather'da asosiy Mini App bo'lmasa ham ishlaydi)
                b = {"text": b["text"], "url": f"https://t.me/{settings.bot_username}?start={start_param(path)}"}
            new.append(b)
        if new:
            rows.append(new)
    return {"inline_keyboard": rows} if rows else None


async def _expand_admins(items: list) -> list:
    res = []
    for chat_id, text, markup in items:
        if not isinstance(chat_id, _Admins):
            res.append((chat_id, text, markup))
            continue
        for chat, thread in await admin_targets(chat_id.topic):
            private = chat in settings.admin_ids
            res.append((chat, text, markup if private else with_thread(for_group(markup), thread)))
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

    def admins(self, text: str, markup: dict | None = None, topic: str = "boshqa") -> None:
        self.items.append((_Admins(topic), text, markup))  # qayerga ketishi flush() da aniqlanadi

    async def flush(self) -> None:
        items, self.items = self.items, []
        kinds, self.kinds = self.kinds, {}
        muted = await _muted({(items[i][0], k) for i, k in kinds.items()}) if kinds else set()
        items = [it for i, it in enumerate(items) if not (i in kinds and (it[0], kinds[i]) in muted)]
        if any(isinstance(it[0], _Admins) for it in items):
            items = await _expand_admins(items)
        for chat_id, text, markup in items:
            await _sender(chat_id, text, markup)


def fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


async def reset_admin_routing() -> None:
    """Barcha mavzu ulanishlari, admin kanali va KYC guruhini o'chiradi (xabarlar yana shaxsiy keladi)."""
    from sqlalchemy import delete, or_

    from app.db import SessionLocal
    from app.models import AppSetting

    async with SessionLocal() as s, s.begin():
        await s.execute(delete(AppSetting).where(or_(
            AppSetting.key.like(TOPIC_KEY + "%"), AppSetting.key.in_((ADMIN_CHAT_KEY, "_kyc_chat_id")))))


async def reset_once(marker: str) -> None:
    """Deploydan keyin bir marta tozalash (admin so'rovi bilan)."""
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert

    from app.db import SessionLocal
    from app.models import AppSetting

    async with SessionLocal() as s:
        if await s.scalar(select(AppSetting.key).where(AppSetting.key == marker)):
            return
    await reset_admin_routing()
    async with SessionLocal() as s, s.begin():
        await s.execute(insert(AppSetting).values(key=marker, value="1").on_conflict_do_nothing())
    log.info("Admin mavzulari tozalandi (%s)", marker)


BOOSTER_KEY = "_booster_group_id"
_booster_cache: list = [None, 0.0]


async def get_booster_group() -> int | None:
    """Boosterlar guruhi: /booster_guruh bilan belgilanadi (yoki Render'dagi BOOSTER_GROUP_ID)."""
    import time

    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import AppSetting

    if time.monotonic() - _booster_cache[1] < 30:
        return _booster_cache[0]
    try:
        async with SessionLocal() as s:
            v = await s.scalar(select(AppSetting.value).where(AppSetting.key == BOOSTER_KEY))
        val = int(v) if v else (settings.booster_group_id or None)
    except Exception:  # noqa: BLE001
        log.exception("Booster guruhini o'qib bo'lmadi")
        val = settings.booster_group_id or None
    _booster_cache[:] = [val, time.monotonic()]
    return val


async def set_booster_group(chat_id: int | None) -> None:
    from sqlalchemy import delete
    from sqlalchemy.dialects.postgresql import insert

    from app.db import SessionLocal
    from app.models import AppSetting

    async with SessionLocal() as s, s.begin():
        if chat_id is None:
            await s.execute(delete(AppSetting).where(AppSetting.key == BOOSTER_KEY))
        else:
            await s.execute(insert(AppSetting).values(key=BOOSTER_KEY, value=str(chat_id))
                            .on_conflict_do_update(index_elements=["key"], set_={"value": str(chat_id)}))
    _booster_cache[:] = [chat_id, 0.0]
