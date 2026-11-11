"""Yangi versiya joylanganda adminlarga bir marta xabar yuboriladi (o'zgarishlar ro'yxati)."""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

log = logging.getLogger(__name__)

RELEASE = "2026-11-12.wallet-id"
NOTES = """🆕 Hamyon yangilandi

🆔 Har bir foydalanuvchiga hamyon ID berildi (masalan VX 4821 7730) — Hamyon va Sozlamalarda ko'rinadi
   Admin panel → Foydalanuvchilar: hamyon ID bo'yicha qidirish mumkin

💼 Pul yechish qaytdi — faqat ishlab topilgan pul uchun:
   • sotuvchi (akkaunt sotuvi), ijaraga beruvchi, booster daromadi yechiladi
   • to'ldirilgan pul yechilmaydi (kartadan kartaga «yuvish»ga yo'l qo'yilmaydi)
   • «Yechish» tabi faqat daromadi bor foydalanuvchilarga ko'rinadi
   • so'rovlar avvalgidek Admin panel → 💸 Yechish'da"""


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
