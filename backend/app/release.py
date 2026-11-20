"""Yangi versiya joylanganda adminlarga bir marta xabar yuboriladi (o'zgarishlar ro'yxati)."""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

log = logging.getLogger(__name__)

RELEASE = "2026-11-20.media-db"
NOTES = """🖼 Yuklangan rasm va videolar endi bazada saqlanadi — deploy qilinganda yo'qolmaydi (video chegarasi 20 MB)
   ⚠️ Eski (shu yangilanishgacha yuklangan) rasmlar server diskida edi — ular allaqachon yo'qolgan bo'lishi mumkin; e'lon egalari qayta yuklaydi
🏆 Turnirlar: jamoaviy (5v5) format — jamoani sardor ro'yxatdan o'tkazadi (kamida 5 a'zo); turnir setkasi (olimpiya tizimi)
   Admin → Turnirlar → «Setka»: yaratish va g'olibni belgilash; final g'olibiga (jamoaning hammasiga) ball avtomatik
🎁 Vaucher kodlari: Roblox, Steam Wallet va boshqa kod beriladigan mahsulotlar sotuvda — kod botda va «Xaridlar tarixi»da
🔎 Arena → Qidiruv: 5v5 jamoaviy bahs, 1v1 duel, rankedga sherik, jamoa (o'yinchi kerak / jamoa kerak / jamoalar)
   Haqiqiy jamoalar: sardor, 7 tagacha a'zo, o'rtacha rank, qo'shilish so'rovi va taklif; viloyat va «Menga mos rank» filtri
   🔔 Sherik signali (mos sherik chiqsa bot xabar beradi), 🤝 Hurmat (birga o'ynaganlarni baholash, so'kinadiganlar belgilanadi)
📊 Tirik MLBB statistikasi (Rone Arena): Qahramonlar → «Tier» (S–D, rank va kun bo'yicha, jadval), qahramon sahifasida g'alaba/tanlov/ban %,
   kuchli raqiblar va yaxshi juftlar; Arena → «Bu hafta kuchayganlar». O'chirish: Sozlamalar → «Tirik MLBB statistikasi»
   ⚠️ Rone Arena tijoriy foydalanish uchun egasi bilan kelishishni so'raydi: arena.rone.dev
📖 Qahramonlar ensiklopediyasi (Arena → O'yinlar yoki /qahramonlar): 124 qahramon, skillar, tavsiya buyumlar,
   counter va eng yaxshi juft, raqib jamoasiga counter-pick, 68 buyum — rasmiy mobilelegends.com ma'lumoti
🔗 MLBB akkauntni ulash: Game ID + server o'yinda tekshiriladi, nik avtomatik olinadi (✓ tasdiqlangan)

🏆 Arena yangilandi (rasmiy MLBB rasmlari bilan):
   🪪 MLBB kartasi — rank nishoni, liniya, 3 ta sevimli qahramon (reyting va jamoa e'lonlarida ko'rinadi)
   🧠 «Qahramonni top» — kuniga 5 savol (qahramonni rasmidan topish, rolini topish), har to'g'ri javob +10 ball
   👑 Haftaning qahramoni — har hafta ovoz, jamoatchilik meta reytingi (+5 ball)
   🤝 Jamoa e'lonlari: liniya ikonkalari, rank nishoni, qahramonlar
🎬 Hamkor: shaxsiy promo-kod (tomoshabinga bonus, hamkorga ball), hamkorlar reytingi, video g'oyalari va heshteglar
🚀 Boost / Savdo / Ijara: rasmiy rank nishonlari, liniya ikonkalari, qahramon tanlash
💻 Admin panel: Sozlamalar → Admin panel → «Mobil» yoki «Web (kompyuter)» — keng ekran, yon menyu
   Botda /administ → «💻 Web havolasi». Yangi bo'lim: Admin → «Arena: viktorina va ovozlar»
🤖 Bot menyusi: /arena, /donat, /hamyon; /start da bo'limlarga tezkor tugmalar
⚙️ Ball miqdorlari: Admin → Sozlamalar → «Arena: ball», promo-kod bonusi → «Hamkor dasturi»

💎 Donat katalogi (oldingi yangilanish):
   🎮 Bosh sahifa yangilandi: 3 ta asosiy o'yin + mashhur o'yinlar (4×2). Faqat donat qoldi; boshqa bo'limlar yashirin
   (Admin → Sozlamalar → «Bo'limlar» dan qayta yoqiladi). Magic Chess yashirildi.
🔌 Bir nechta donat API: Admin → Donat → API → «+ API qo'shish» (kalit shifrlanadi). Katalog va narxlar API'dan avtomatik (har 30 daqiqa)
   O'yinlar: Admin → Donat → O'yinlar (ko'rinish, asosiy/mashhur). Narx: dollar kursi va ustama «API» tabida
   ⚠️ Yupay'da sinov yo'q — birinchi buyurtmani eng arzon nominalda sinang

💎 Yupay Merchant API ulandi (hujjat asosida): ID tekshiruvi, avtomatik buyurtma, holat kuzatuvi, vebhuk, depozit ogohlantirishi
   Render: DONATE_PROVIDER=yupay, DONATE_PROVIDER_KEY=ypk_…   ·   Admin → Donat → «Donat API»
   Paketlarga SKU: Admin → Donat paketlari → «Yupay katalogidan tanlash»
   ⚠️ Yupay'da sinov yo'q: har buyurtma haqiqiy pul yechadi — avval eng arzon nominalda sinang

🔌 Donat API ulashga tayyor: Admin → Donat → «Donat API» kartasi (holat, ulanishni tekshirish, yo'riqnoma)
   Render'da DONATE_PROVIDER=http, DONATE_PROVIDER_URL, DONATE_PROVIDER_KEY (+ sarlavha va yo'llar sozlamalari). docs/DONAT_API.md

🔒 Ilova hozir YOPIQ: faqat adminlar kira oladi, boshqalarga /start da «Tez kunda ochilamiz!» chiqadi
   Hamma uchun ochish: botda /ochish   ·   yana yopish: /yopish

📢 Akkaunt e'lonlari kanalga avtomatik: botni kanalga admin qiling va kanalda yozing /elon_kanal
   Tasdiqlangan e'lon → kanalda post («🛒 Sotib olish»), to'lansa «BAND», sotilsa «SOTILDI»

🛠 Admin panelga yangi bo'limlar (Admin → Boshqaruv):
   📈 Daromad va grafik — kunlik daromad, to'ldirish, aylanma, yangi foydalanuvchilar
   📣 Ommaviy xabar — hammaga / faollarga / sotuvchilarga…, avval o'zingizga sinov
   🎟 Promo-kodlar — hamyonga bonus (foydalanuvchi: Hamyon → «Promo-kod bormi?»)
   🧾 Admin jurnali — kim, qachon, kimga, qancha
   👥 Foydalanuvchi kartochkasi — barcha to'lov va xaridlari bitta joyda
📊 Kunlik hisobot har kuni 09:00 da — guruhda /mavzu → «Kunlik hisobot»

💳 Kirimni aniq odamga yozish: Admin → Kirimlar → «Kimga» (VX hamyon ID yoki Telegram ID) → summa
   Biriktirilmagan kirimlarda ham «Odamga yozish» tugmasi bor

🛠 Admin panel yangilandi: bosh sahifada «Navbat» (ishlar soni bilan) va «Boshqaruv» bo'limlari
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
