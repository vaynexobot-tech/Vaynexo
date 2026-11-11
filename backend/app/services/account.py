"""Profil xavfsizligi: identifikatsiya (KYC), PIN-kod, biometrik kirish, saqlangan kartalar."""

import logging
import re
import secrets
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError, BadState
from app.models import PaymentCard, User
from app.security import check_secret, encrypt, hash_secret
from app.services.notify import Outbox

log = logging.getLogger(__name__)

KYC_LABELS = ("Hujjat bilan rasm (selfi)", "Pasport oldi", "Pasport orqasi")


# ---------------------------------------------------------------- Identifikatsiya
async def send_kyc_to_admins(user: User, images: list[bytes]) -> None:
    """Rasmlar faqat adminlarga Telegram orqali yuboriladi — serverda saqlanmaydi."""
    from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

    from app.bot.instance import get_bot

    bot = get_bot()
    media = [
        InputMediaPhoto(media=BufferedInputFile(img, f"kyc_{user.id}_{i}.jpg"), caption=KYC_LABELS[i])
        for i, img in enumerate(images)
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"kyc:ok:{user.id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"kyc:no:{user.id}"),
    ]])
    who = f"@{user.username}" if user.username else user.first_name
    targets = [settings.admin_chat_id] if settings.admin_chat_id else list(settings.admin_ids)
    if not targets:
        raise AppError("no_admin", "Admin sozlanmagan, keyinroq urinib ko'ring", 503)
    for chat_id in targets:
        await bot.send_media_group(chat_id, media)
        await bot.send_message(chat_id, f"🪪 Identifikatsiya so'rovi\n{who} · ID {user.id}", reply_markup=kb)


async def kyc_submit(session: AsyncSession, user_id: int, images: list[bytes]) -> User:
    if len(images) != 3:
        raise AppError("kyc_files", "Uchala rasmni yuklang")
    async with session.begin():
        user = await session.get(User, user_id, with_for_update=True)
        if user.kyc_status == "verified":
            raise BadState("Siz allaqachon tasdiqlangansiz")
        if user.kyc_status == "pending":
            raise BadState("So'rovingiz tekshirilmoqda")
    await send_kyc_to_admins(user, images)
    async with session.begin():
        user = await session.get(User, user_id, with_for_update=True)
        user.kyc_status, user.kyc_note, user.kyc_at = "pending", None, datetime.now(timezone.utc)
    return user


async def kyc_resolve(session: AsyncSession, user_id: int, approve: bool, note: str | None, out: Outbox) -> User:
    async with session.begin():
        user = await session.get(User, user_id, with_for_update=True)
        if user is None:
            raise AppError("not_found", "Foydalanuvchi topilmadi", 404)
        if user.kyc_status != "pending":
            raise BadState("Bu so'rov allaqachon ko'rib chiqilgan")
        user.kyc_status = "verified" if approve else "rejected"
        user.kyc_note = None if approve else (note or "Rasmlar aniq emas yoki talabga mos emas")
        user.kyc_at = datetime.now(timezone.utc)
    if approve:
        out.user(user.id, "✅ Shaxsingiz tasdiqlandi! Endi profilingizda «Tasdiqlangan» belgisi ko'rinadi.")
    else:
        out.user(user.id, f"❌ Identifikatsiya rad etildi.\nSabab: {user.kyc_note}\nRasmlarni qaytadan yuborishingiz mumkin.")
    return user


async def require_kyc(session: AsyncSession, user_id: int, area: str) -> None:
    """Sozlamada majburiy bo'lsa (kyc_marketplace / kyc_rental), tasdiqlanmagan foydalanuvchini to'xtatadi."""
    from app.services import app_settings

    if await app_settings.get_value(session, f"kyc_{area}") != "on":
        return
    status = await session.scalar(select(User.kyc_status).where(User.id == user_id))
    if status != "verified":
        raise AppError("kyc_required", "Avval shaxsingizni tasdiqlang (Sozlamalar → Identifikatsiya)", 403)


# ---------------------------------------------------------------- PIN va biometriya
def _check_pin_format(pin: str) -> None:
    if not re.fullmatch(r"\d{4}", pin or ""):
        raise AppError("bad_pin", "PIN 4 ta raqamdan iborat bo'lsin")
    if pin in ("0000", "1111", "1234", "4321") or len(set(pin)) == 1:
        raise AppError("weak_pin", "Juda oson PIN. Boshqa raqamlar tanlang")


async def set_pin(session: AsyncSession, user_id: int, pin: str, old_pin: str | None) -> User:
    _check_pin_format(pin)
    async with session.begin():
        user = await session.get(User, user_id, with_for_update=True)
        if user.pin_hash and not check_secret(old_pin or "", user.pin_hash):
            raise AppError("wrong_pin", "Joriy PIN noto'g'ri", 403)
        user.pin_hash = hash_secret(pin)
        user.pin_ver += 1
        user.bio_hash = None  # PIN almashsa, biometriya qaytadan yoqiladi
    return user


async def remove_pin(session: AsyncSession, user_id: int, pin: str) -> User:
    async with session.begin():
        user = await session.get(User, user_id, with_for_update=True)
        if not user.pin_hash:
            return user
        if not check_secret(pin or "", user.pin_hash):
            raise AppError("wrong_pin", "PIN noto'g'ri", 403)
        user.pin_hash, user.bio_hash = None, None
        user.pin_ver += 1
    return user


async def enable_bio(session: AsyncSession, user_id: int) -> str:
    """Qurilmaning biometrik xotirasiga yoziladigan kalit. Serverda faqat xeshi saqlanadi."""
    key = secrets.token_urlsafe(32)
    async with session.begin():
        user = await session.get(User, user_id, with_for_update=True)
        if not user.pin_hash:
            raise BadState("Avval PIN-kod o'rnating")
        user.bio_hash = hash_secret(key)
    return key


async def disable_bio(session: AsyncSession, user_id: int) -> None:
    async with session.begin():
        await session.execute(update(User).where(User.id == user_id).values(bio_hash=None))


# ---------------------------------------------------------------- Kartalar
def card_brand(number: str) -> str:
    if number.startswith(("8600", "5614")):
        return "Uzcard"
    if number.startswith("9860"):
        return "Humo"
    if number.startswith("4"):
        return "Visa"
    if number[:2] in ("51", "52", "53", "54", "55") or 2221 <= int(number[:4]) <= 2720:
        return "Mastercard"
    return "Karta"


def card_dict(c: PaymentCard) -> dict:
    return {"id": c.id, "last4": c.last4, "brand": c.brand, "holder": c.holder, "expiry": c.expiry, "is_default": c.is_default}


async def list_cards(session: AsyncSession, user_id: int) -> list[PaymentCard]:
    return list(await session.scalars(
        select(PaymentCard).where(PaymentCard.user_id == user_id).order_by(PaymentCard.is_default.desc(), PaymentCard.id)
    ))


async def add_card(session: AsyncSession, user_id: int, number: str, holder: str, expiry: str) -> PaymentCard:
    number = re.sub(r"\D", "", number or "")
    if len(number) != 16:
        raise AppError("bad_card", "Karta raqami 16 ta raqam bo'lsin")
    expiry = (expiry or "").strip()
    if expiry and not re.fullmatch(r"(0[1-9]|1[0-2])/\d{2}", expiry):
        raise AppError("bad_expiry", "Amal qilish muddati MM/YY ko'rinishida bo'lsin")
    async with session.begin():
        cards = await list_cards(session, user_id)
        if len(cards) >= 5:
            raise AppError("too_many", "Ko'pi bilan 5 ta karta saqlash mumkin")
        if any(c.last4 == number[-4:] and c.brand == card_brand(number) for c in cards):
            raise AppError("dup_card", "Bu karta allaqachon qo'shilgan")
        card = PaymentCard(
            user_id=user_id, number_enc=encrypt(number), last4=number[-4:], brand=card_brand(number),
            holder=(holder or "").strip().upper()[:64], expiry=expiry, is_default=not cards,
        )
        session.add(card)
    return card


async def set_default_card(session: AsyncSession, user_id: int, card_id: int) -> None:
    async with session.begin():
        card = await session.get(PaymentCard, card_id)
        if not card or card.user_id != user_id:
            raise AppError("not_found", "Karta topilmadi", 404)
        await session.execute(update(PaymentCard).where(PaymentCard.user_id == user_id).values(is_default=False))
        card.is_default = True


async def delete_card(session: AsyncSession, user_id: int, card_id: int) -> None:
    async with session.begin():
        card = await session.get(PaymentCard, card_id)
        if not card or card.user_id != user_id:
            raise AppError("not_found", "Karta topilmadi", 404)
        was_default = card.is_default
        await session.delete(card)
        await session.flush()
        if was_default:
            rest = await list_cards(session, user_id)
            if rest:
                rest[0].is_default = True
