# Donat API — admin paneldan (bir nechta API)

Hujjat (Yupay): https://reseller.yupay.uz/uz/docs · API: `https://api.yupay.uz/merchant/v1`

## ⚠️ Muhim
- Yupay'da **sinov muhiti yo'q**: har bir buyurtma haqiqiy pul yechadi. Birinchi sinov — eng arzon nominal.
- API narxi **USD**da, foydalanuvchi **so'm**da to'laydi. So'm narx = tannarx × dollar kursi × (1 + ustama%), 100 so'mga yuqoriga yaxlitlanadi.
- Kalitni chatga yubormang. Kalit admin panelga kiritiladi, serverda **shifrlanadi**, qayta ko'rsatilmaydi.

## Ulash
1. Yupay kabinet → **Sozlamalar → Kalit yaratish** (`ypk_…`). Kalitning **IP ro'yxatini bo'sh** qoldiring.
2. Mini App → **Admin → 💎 Donat → API → «+ API qo'shish»**: nom, kalit → Saqlash.
3. **Tekshirish** — depozit summasi chiqsa, ulandi.
4. **Katalogni yangilash** — o'yinlar, paketlar va narxlar API'dan olinadi (keyin har 30 daqiqada o'zi).
5. **Donat → O'yinlar**: yangi topilgan o'yinlar yashirin. «Ko'rinadi» ni yoqing, **Asosiy** (1–3 — katta kartalar) yoki **Mashhur** (4×2 to'r) belgilang.
6. **Narx hisoblash**: dollar kursi va ustamani kiriting → «Saqlash va narxlarni yangilash».

Bir nechta API qo'shsa bo'ladi (har bir o'yin o'z API'si orqali yetkaziladi). «Boshqa API» turi — oddiy HTTP API: paketlar qo'lda kiritiladi (Donat paketlari).

## Qanday ishlaydi
- ID tekshiruvi: Yupay `POST /validate/player` (nik ko'rsatiladi). Tekshirib bo'lmasa — buyurtmaga ruxsat beriladi.
- Buyurtma: `merchant_order_id = VX-D{id}` (idempotent). Holat: `delivered` → tayyor; `paid/fulfilling/fulfillment_delayed` → kutiladi; `failed` + to'liq qaytarilgan → foydalanuvchiga pul qaytadi; qisman → adminga «tekshiruv».
- Yupay rad etsa (depozit yetmadi, narx o'zgardi, nominal tugadi) → pul foydalanuvchiga qaytadi, adminga sabab yoziladi.
- Depozit `DONATE_LOW_BALANCE_USD` (standart $20) dan kamaysa guruhga ogohlantirish keladi.
- Vebhuk (ixtiyoriy, tezroq natija): API kartasidagi «Vebhuk manzili»ni Yupay kabinetiga yozing.

## Bo'limlar
Standart holatda ilovada **faqat donat** (+ hamyon, tarix, sozlamalar). Boshqa bo'limlar (Account savdo, ijara, boost, TG, arena, hamkor, AI, top) Admin → Sozlamalar → «Bo'limlar» dan yoqiladi.

## Eski usul (Render o'zgaruvchilari)
`DONATE_PROVIDER=yupay` + `DONATE_PROVIDER_KEY` hali ishlaydi (bog'lanmagan paketlar uchun), lekin admin paneldagi usul qulayroq.
