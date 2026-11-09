"""Bot: Mini App'ni ochish, admin uchun bank xabarini qabul qilish, boosterlar guruhi."""

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo,
)
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.errors import AppError
from app.models import BoostOrder, User
from app.queue import enqueue
from app.security import decrypt
from app.services import p2p
from app.services import services as svc
from app.services.notify import Outbox, fmt

log = logging.getLogger(__name__)
router = Router()


def open_app_kb(text: str = "🎮 VAYNEXO ni ochish", path: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=text, web_app=WebAppInfo(url=settings.webapp_url.rstrip("/") + path))
    ]])


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


async def ensure_user(tg_user, ref: int | None = None) -> User:
    async with SessionLocal() as session, session.begin():
        user = await session.get(User, tg_user.id)
        if user is None:
            if ref and (ref == tg_user.id or not await session.get(User, ref)):
                ref = None
            user = User(
                id=tg_user.id, username=tg_user.username, first_name=(tg_user.first_name or "")[:128],
                lang="ru" if (tg_user.language_code or "").startswith("ru") else "uz",
                referrer_id=ref, is_admin=is_admin(tg_user.id),
            )
            session.add(user)
        elif user.username != tg_user.username:
            user.username = tg_user.username
    return user


@router.message(CommandStart(), F.chat.type == "private")
async def start(message: Message, command: CommandObject):
    ref = None
    if command.args and command.args.startswith("ref_") and command.args[4:].isdigit():
        ref = int(command.args[4:])
    await ensure_user(message.from_user, ref)
    await message.answer(
        "Assalomu alaykum! 👋\n\nVAYNEXO — raqamli o'yin bozori:\n"
        "💎 Mobile Legends va Magic Chess almaz donat\n🛒 Akkaunt savdo (garant bilan)\n"
        "🚀 Rank boost\n⭐️ Telegram Premium, Stars, Gift\n🏆 Turnirlar\n\nBoshlash uchun pastdagi tugmani bosing.",
        reply_markup=open_app_kb(),
    )


@router.message(Command("help"), F.chat.type == "private")
async def help_cmd(message: Message):
    await message.answer("Savollar bo'yicha: @vaynexo_support\nIlovani ochish:", reply_markup=open_app_kb())


@router.message(Command("stats"), F.chat.type == "private")
async def stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    async with SessionLocal() as session:
        users = await session.scalar(select(func.count()).select_from(User))
        unmatched = await p2p.unmatched_count(session)
    await message.answer(f"👥 Foydalanuvchilar: {users}\n⚠️ Biriktirilmagan kirimlar: {unmatched}",
                         reply_markup=open_app_kb("Admin panel", "/admin"))


@router.message(Command("id"))
async def chat_id(message: Message):
    """Guruh ID sini bilish uchun (BOOSTER_GROUP_ID / ADMIN_CHAT_ID)."""
    await message.answer(f"Chat ID: {message.chat.id}")


@router.message(F.chat.type == "private", F.text | F.caption)
async def admin_bank_forward(message: Message):
    """Admin bank bildirishnomasini (Humo/Uzcard bot, SMS) botga forward qiladi — kirim avtomatik topiladi."""
    if not is_admin(message.from_user.id):
        await message.answer("Ilovani ochish uchun tugmani bosing 👇", reply_markup=open_app_kb())
        return
    text = message.text or message.caption or ""
    amount = p2p.parse_bank_message(text)
    if not amount:
        await message.answer("Bu xabardan kirim summasi topilmadi.")
        return
    origin = message.forward_origin
    origin_date = getattr(origin, "date", None) or message.date
    out = Outbox()
    async with SessionLocal() as session, session.begin():
        inc = await p2p.register_incoming(
            session, amount, "bot_forward", out, raw_text=text, external_id=f"fwd:{origin_date.isoformat()}:{amount}:{text[:200]}"
        )
    await out.flush()
    if inc is None:
        await message.answer(f"ℹ️ Bu kirim oldin qayd etilgan ({fmt(amount)}).")
    elif inc.status == "matched":
        await message.answer(f"✅ {fmt(amount)} — so'rov #{inc.topup_id} ga biriktirildi, balans to'ldirildi.")
    else:
        await message.answer(f"⚠️ {fmt(amount)} — mos so'rov topilmadi. Admin paneldan biriktiring.",
                             reply_markup=open_app_kb("Admin panel", "/admin"))


# ------------------------------------------------------------------ boosterlar guruhi
def boost_post_text(o: BoostOrder) -> str:
    status = {"searching": "🟢 YANGI", "accepted": "🟡 Olingan", "in_progress": "🔵 Jarayonda", "finished": "🏁 Tugatildi",
              "done": "✅ Yakunlandi", "refunded": "⛔️ Bekor qilindi", "disputed": "⚖️ Nizo"}.get(o.status, o.status)
    lines = [
        f"Buyurtma #{o.id} · {status}",
        f"Xizmat: Rank boost ({o.game})",
        f"Rank: {o.current_rank} → {o.target_rank}",
        f"Yulduz: {o.stars}",
        f"Liniya: {o.lane or 'Ixtiyoriy'}",
        f"Kirish: {o.login_method}",
        f"Booster ulushi: {fmt(o.price * svc.BOOSTER_SHARE_PERCENT // 100)}",
    ]
    if o.note:
        lines.append(f"Izoh: {o.note}")
    if o.booster_name:
        lines.append(f"Booster: {o.booster_name}")
    return "\n".join(lines)


def boost_post_kb(o: BoostOrder) -> InlineKeyboardMarkup | None:
    if o.status != "searching":
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"boost:accept:{o.id}")]])


def booster_dm_kb(o: BoostOrder) -> InlineKeyboardMarkup | None:
    if o.status == "accepted":
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Ishni boshladim", callback_data=f"boost:start:{o.id}")]])
    if o.status == "in_progress":
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏁 Tugatdim", callback_data=f"boost:finish:{o.id}")]])
    return None


@router.callback_query(F.data.startswith("boost:"))
async def boost_callback(cb: CallbackQuery):
    _, action, oid = cb.data.split(":")
    order_id = int(oid)
    booster = await ensure_user(cb.from_user)
    out = Outbox()
    try:
        async with SessionLocal() as session, session.begin():
            if action == "accept":
                order = await svc.boost_accept(session, order_id, booster, out)
            else:
                order = await svc.boost_progress(session, order_id, booster.id, action, out)
            creds = decrypt(order.credentials_enc) if action == "accept" else None
    except AppError as e:
        await cb.answer(e.message, show_alert=True)
        return
    await out.flush()
    if action == "accept":
        dm = boost_post_text(order) + (f"\n\n🔐 Kirish ma'lumotlari:\n{creds}" if creds else
                                       "\n\nMijoz bilan bog'lanish uchun admin bilan aloqa qiling.")
        try:
            await cb.bot.send_message(booster.id, dm, reply_markup=booster_dm_kb(order))
            await cb.answer("Buyurtma sizniki ✅ Tafsilotlar shaxsiy xabarda.")
        except Exception:
            log.warning("Boosterga DM yuborilmadi (botni /start qilmagan bo'lishi mumkin)")
            await cb.answer("Buyurtma sizniki, lekin shaxsiy xabar yuborilmadi: botga /start yozing va adminga murojaat qiling.", show_alert=True)
            out.admins(f"⚠️ Booster {booster.id} buyurtma #{order_id} ni oldi, lekin DM yuborilmadi.")
            await out.flush()
    else:
        await cb.answer("Bajarildi ✅")
        try:
            await cb.message.edit_reply_markup(reply_markup=booster_dm_kb(order))
        except Exception:
            pass
    await enqueue("update_boost_post", order_id)
