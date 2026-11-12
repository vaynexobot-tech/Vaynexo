"""Yangi versiya joylanganda adminlarga bir marta xabar yuboriladi (o'zgarishlar ro'yxati)."""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

log = logging.getLogger(__name__)

RELEASE = "2026-11-12.admin-menyu"
NOTES = """🛠 Admin panel yangilandi: bosh sahifada «Navbat» (ishlar soni bilan) va «Boshqaruv» bo'limlari
   Navbatga qo'shildi: «To'ladim» to'lovlari, identifikatsiya, hamkor videolari, ijara

🐞 Tuzatildi: bot tugmasidan TG buyurtma sahifasi ochilmasligi (404), xaridlar tarixidagi jami summa,
   e'lon berishda identifikatsiya ogohlantirishi oldindan ko'rinadi

💎 Donat endi QO'LDA bajariladi (API ulanguncha)
   Har buyurtma guruhdagi «buyurtma» mavzusiga keladi: almazni tashlang → «✅ Bajarildi» yoki «↩️ Pulni qaytarish»
   (avval sinov rejimi edi — pul yechilib, almaz yuborilmas edi)

🤖 AI bo'limi «Tez kunda» qilib qo'yildi

🗂 Admin guruhida mavzular: har bir mavzuga o'z xabarlari
   Botni guruhga admin qiling, har mavzuda yozing: /mavzu elon, /mavzu tolov, /mavzu yechish, /mavzu nizo, /mavzu kyc, /mavzu barcha …
   Ro'yxat: guruhda /mavzu

📢 Admin xabarlarini kanal/guruhga ulash
   Botni kanalga admin qilib qo'shing va kanalda yozing: /admin_kanal
   (guruhda ham ishlaydi; bekor qilish: /admin_kanal_ochir)
   Yangi e'lonlar, to'lovlar, pul yechish, nizolar, identifikatsiya — hammasi shu yerga keladi

🐞 Chatda xabar yuborganda ilova qorayib qolishi tuzatildi

🆕 To'lov kartalari: summa o'zgarmaydi

💳 Har bir to'ldirishga bitta bo'sh karta beriladi — foydalanuvchi aynan o'zi yozgan summani o'tkazadi (50 000 → 50 000)
   • bir xil summa bir vaqtda turli kartalarga taqsimlanadi
   • faqat hamma kartada shu summa band bo'lsa: +100 so'm qadam (50 100, 50 200 …), mayda summa yo'q
   • kartalarni qo'shish: Admin panel → To'lov kartalari (18 ta va undan ko'p)

🤖 Telefonsiz avtomatik tasdiqlash: Admin panel → To'lovlar → «Bank botlari (Telegram)»
   server @HUMOcardbot va @CardXabarBot xabarlarini o'zi o'qiydi («To'ladim» bosilsa darhol)

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
