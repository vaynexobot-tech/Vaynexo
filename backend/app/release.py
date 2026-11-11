"""Yangi versiya joylanganda adminlarga bir marta xabar yuboriladi (o'zgarishlar ro'yxati)."""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

log = logging.getLogger(__name__)

RELEASE = "2026-11-11.arena-hamkor"
NOTES = """🆕 VAYNEXO yangilandi

🤝 Hamkor dasturi — video havolasi yuboriladi, admin ko'rishlarni kiritib tasdiqlaydi, mukofot avtomatik
🏆 Arena: Turnirlar · Jamoa · Reyting · Vazifalar
  • ball tizimi (pulga almashtirilmaydi), kunlik/haftalik vazifalar
  • ballni almashtirish: Boost chegirmasi, VIP 3 kun, turnirga bepul kirish
  • bepul prognoz (admin o'yin qo'shadi va natijani kiritadi)
  • jamoa topish e'lonlari (7 kun), sezon reytingi
🚀 Boost: yulduz narxlari daraja bo'yicha, jonli progress (/progress)
🔑 Ijara: 24 soat −10%, 3 kun −20%, 1 hafta −30%, depozit 50 000
⭐️ Stars paketlariga bonus yulduz
🪪 Account savdo va ijara uchun identifikatsiya majburiy (admin paneldan o'chirsa bo'ladi)
💼 Garant xizmat haqi 0%, to'ldirish limiti 500 000 (Silver)

Yangi buyruqlar: /administ — tezkor vazifalar, /booster — boosterlar uchun.
Barcha narx va foizlar: Admin panel → Sozlamalar."""


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
