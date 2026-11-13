"""Akkaunt savdo e'lonlari → Telegram kanal.

Tasdiqlangan e'lon kanalga post bo'ladi («🛒 Sotib olish» tugmasi botdagi e'lonni ochadi),
band bo'lsa / sotilsa / narx o'zgarsa post yangilanadi, olib tashlansa o'chiriladi.
Har daqiqa sync_batch() holati o'zgargan e'lonlarni tekshiradi (bir yo'la ko'pi bilan BATCH ta).
"""

import hashlib
import html
import logging

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting, Listing

log = logging.getLogger(__name__)
KEY = "_listing_channel"
BATCH = 5
GAMES = {"ML": "Mobile Legends", "MC": "Magic Chess"}
SHOWN = ("active", "reserved", "sold")


async def get_channel() -> int | None:
    async with SessionLocal() as s:
        v = await s.scalar(select(AppSetting.value).where(AppSetting.key == KEY))
    return int(v) if v else None


async def set_channel(chat_id: int | None) -> None:
    async with SessionLocal() as s, s.begin():
        if chat_id is None:
            await s.execute(delete(AppSetting).where(AppSetting.key == KEY))
        else:
            await s.execute(insert(AppSetting).values(key=KEY, value=str(chat_id))
                            .on_conflict_do_update(index_elements=["key"], set_={"value": str(chat_id)}))
        # boshqa kanalga o'tilsa — postlar yangidan chiqadi
        await s.execute(update(Listing).values(channel_msg_id=None, channel_state=None))


def caption(l: Listing) -> str:
    e = html.escape
    head = {"reserved": "🔒 <b>BAND</b> — xaridor to'lov qildi\n\n", "sold": "✅ <b>SOTILDI</b>\n\n"}.get(l.status, "")
    lines = [
        f"{head}🎮 {GAMES.get(l.game, l.game)} · <b>{e(l.rank.upper())}</b>",
        f"<b>{e(l.title)}</b>",
        "",
        f"⭐️ Rank: {e(l.rank)}" + (f" · 🏆 {e(l.collection_level)}" if l.collection_level else ""),
        f"🧥 Skin: {l.skins} · 🦸 Qahramon: {l.heroes}" + (f" · 🌍 {e(l.server)}" if l.server else ""),
    ]
    if l.description:
        d = l.description.strip()
        lines += ["", e(d[:300] + ("…" if len(d) > 300 else ""))]
    lines += ["", f"💰 Narx: <b>{l.price:,} so'm</b>".replace(",", " "), "🛡 Garant orqali xavfsiz savdo",
              "", f"#{l.game} #{l.rank.replace(' ', '')} #e{l.id}"]
    return "\n".join(lines)[:1000]


def keyboard(l: Listing) -> dict | None:
    if l.status != "active" or not settings.bot_username:
        return None
    url = f"https://t.me/{settings.bot_username}?start=listing_{l.id}"
    return {"inline_keyboard": [[{"text": "🛒 Sotib olish", "url": url}]]}


def photo_url(l: Listing) -> str | None:
    for m in l.media or []:
        if m.get("type") == "image" and m.get("url"):
            u = m["url"]
            return u if u.startswith("http") else settings.webapp_url.rstrip("/") + u
    return None


def state_of(l: Listing) -> str:
    raw = f"{l.status}|{l.price}|{l.title}|{l.description}|{l.rank}|{l.skins}|{l.heroes}|{bool(settings.bot_username)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


# --- Telegram chaqiriqlari (testlarda almashtiriladi)
class TgApi:
    async def post(self, chat: int, photo: str | None, text: str, kb: dict | None) -> tuple[int, str]:
        from app.bot.instance import get_bot

        bot = get_bot()
        if photo:
            try:
                m = await bot.send_photo(chat, photo, caption=text, parse_mode="HTML", reply_markup=kb)
                return m.message_id, "p"
            except Exception:  # noqa: BLE001 — rasm ochilmasa, matn bilan
                log.warning("Kanalga rasm yuborilmadi, matn yuboriladi", exc_info=True)
        m = await bot.send_message(chat, text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        return m.message_id, "t"

    async def edit(self, chat: int, msg_id: int, kind: str, text: str, kb: dict | None) -> None:
        from app.bot.instance import get_bot

        bot = get_bot()
        try:
            if kind == "p":
                await bot.edit_message_caption(chat_id=chat, message_id=msg_id, caption=text, parse_mode="HTML", reply_markup=kb)
            else:
                await bot.edit_message_text(text, chat_id=chat, message_id=msg_id, parse_mode="HTML", reply_markup=kb,
                                            disable_web_page_preview=True)
        except Exception as e:  # noqa: BLE001
            if "not modified" not in str(e):
                raise

    async def delete(self, chat: int, msg_id: int) -> None:
        from app.bot.instance import get_bot

        try:
            await get_bot().delete_message(chat, msg_id)
        except Exception:  # noqa: BLE001 — eski post o'chmasa ham davom etamiz
            log.info("Kanal posti o'chirilmadi: %s", msg_id)


tg = TgApi()


async def sync_batch(limit: int = BATCH) -> int:
    chat = await get_channel()
    if not chat:
        return 0
    done = 0
    async with SessionLocal() as s:
        rows = list(await s.scalars(
            select(Listing).where(or_(
                and_(Listing.status == "active", Listing.channel_msg_id.is_(None)),
                Listing.channel_msg_id.is_not(None),
            )).order_by(Listing.id).limit(500)
        ))
    for l in rows:
        if done >= limit:
            break
        st = state_of(l)
        kind, _, saved = (l.channel_state or "").partition(":")
        try:
            if l.channel_msg_id is None:
                if l.status != "active":
                    continue
                msg_id, kind = await tg.post(chat, photo_url(l), caption(l), keyboard(l))
                new = (msg_id, f"{kind}:{st}")
            elif l.status not in SHOWN:
                await tg.delete(chat, l.channel_msg_id)
                new = (None, None)
            elif saved != st:
                await tg.edit(chat, l.channel_msg_id, kind or "t", caption(l), keyboard(l))
                new = (l.channel_msg_id, f"{kind or 't'}:{st}")
            else:
                continue
        except Exception:  # noqa: BLE001
            log.exception("Kanal bilan sinxronlash xatosi: e'lon #%s", l.id)
            continue
        async with SessionLocal() as s, s.begin():
            await s.execute(update(Listing).where(Listing.id == l.id).values(channel_msg_id=new[0], channel_state=new[1]))
        done += 1
    return done
