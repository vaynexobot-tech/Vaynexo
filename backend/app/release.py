"""Yangi versiya joylanganda adminlarga bir marta xabar yuboriladi (o'zgarishlar ro'yxati)."""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

log = logging.getLogger(__name__)

RELEASE = "2026-11-12.multi-card"
NOTES = """🆕 To'lov kartalari: summa o'zgarmaydi

💳 Har bir to'ldirishga bitta bo'sh karta beriladi — foydalanuvchi aynan o'zi yozgan summani o'tkazadi (50 000 → 50 000)
   • bir xil summa bir vaqtda turli kartalarga taqsimlanadi
   • faqat hamma kartada shu summa band bo'lsa: +100 so'm qadam (50 100, 50 200 …), mayda summa yo'q
   • kartalarni qo'shish: Admin panel → To'lov kartalari (18 ta va undan ko'p)

📩 SMS'da kartaning oxirgi 4 raqami bo'lsa, kirim aynan o'sha kartadagi so'rovga biriktiriladi"""


async def notify_admins_once() -> None:
    if not settings.bot_token or not settings.admin_ids:
        return
    key = "_release_notified"
    try:
        async with SessionLocal() as session, session.begin():
            row = await session.scalar(select(AppSetting).where(AppSetting.key == key).with_for_update())
            if row is not None and row.value == RELEASE:
                return
            await session.execute(insert(AppSetting).values(key=key, value=RELEASE)
                                  .on_conflict_do_update(index_elements=["key"], set_={"value": RELEASE}))
        from app.bot.instance import get_bot

        for admin_id in settings.admin_ids:
            try:
                await get_bot().send_message(admin_id, NOTES)
            except Exception:
                log.warning("Yangilanish xabari %s ga yuborilmadi", admin_id)
    except Exception:
        log.exception("Yangilanish xabarini yuborib bo'lmadi")
