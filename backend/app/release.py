"""Yangi versiya joylanganda adminlarga bir marta xabar yuboriladi (o'zgarishlar ro'yxati)."""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

log = logging.getLogger(__name__)

RELEASE = "2026-11-12.karta-otkazma"
NOTES = """🆕 VAYNEXO yangilandi: to'lov tizimi

💳 Hamyon → «Karta orqali o'tkazma»
  • taymer (standart 10 daqiqa) va noyob summa
  • kartalar ro'yxati, nusxa olish tugmasi bilan
  • «To'ladim» tugmasi va chek yuklash → «Tekshirilmoqda» holati
  • chek sizga botda keladi: ✅ Tasdiqlash / ❌ Rad etish
  • bank SMS'ini botga forward qilsangiz, to'lov avvalgidek avtomatik tasdiqlanadi

⚙️ Admin panel → 💳 Kirimlar:
  • «To'lov kartalari» — kartalarni shu yerda qo'shing/o'chiring
  • «To'ladim — tekshiruvda» ro'yxati
⚙️ Sozlamalar → Hamyon → «To'lov taymeri (daqiqa)»

❗️ Tasdiqlashdan oldin kartaga aynan shu summa tushganini bank ilovasida tekshiring — chek soxta bo'lishi mumkin."""


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
