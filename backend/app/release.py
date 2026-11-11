"""Yangi versiya joylanganda adminlarga bir marta xabar yuboriladi (o'zgarishlar ro'yxati)."""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

log = logging.getLogger(__name__)

RELEASE = "2026-11-12.p2p-avto"
NOTES = """🆕 To'lov endi to'liq avtomatik — chek kerak emas

💳 Foydalanuvchi: summa → noyob summa (masalan 50 037) → kartaga o'tkazadi → «To'ladim»
✅ Bank xabari kelishi bilan balans o'zi to'ldiriladi va botda xabar boradi

Bank xabari qanday keladi (bittasi yetarli):
📲 1) SMS-forwarder: karta SIM'i turgan Android telefonga ilova o'rnatiladi, bank SMS'larini serverga yuboradi.
   Sozlash: Admin panel → 💳 Kirimlar → «Avtomatik tasdiqlash (SMS)» → «Qanday ulash»
🤖 2) Bank SMS'i yoki bank botidagi xabarni shu botga forward qilish — darhol topiladi

⏳ «To'ladim» bosilib, 15 daqiqada bank xabari kelmasa — sizga ✅/❌ tugmalari bilan xabar keladi
(vaqtni Sozlamalar → Hamyon'da o'zgartirasiz)"""


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
