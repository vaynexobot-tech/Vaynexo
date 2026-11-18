# Donat API — Yupay Merchant API

Hujjat: https://reseller.yupay.uz/uz/docs · API: `https://api.yupay.uz/merchant/v1`
Hozir donat QO'LDA (`DONATE_PROVIDER=manual`). Yupay ulangach avtomatik bo'ladi.

## ⚠️ Muhim
- **Sinov muhiti yo'q.** Har bir `POST /orders` haqiqiy xarid qiladi va depozitdan USD yechadi. Birinchi sinov — eng arzon nominal.
- Pul Yupay depozitidan **USD**da yechiladi, foydalanuvchi esa **so'mda** to'laydi. Paket narxi (so'm) Yupay USD narxidan yuqori bo'lsin (kursni hisobga oling).
- Depozitni o'zingiz to'ldirasiz. $20 dan kamaysa guruhga ogohlantirish keladi (`DONATE_LOW_BALANCE_USD`).

## 1. Yupay kabinetida
1. **Sozlamalar → Kalit yaratish** → `ypk_…` (bir marta ko'rsatiladi). Kalitni chatga yubormang.
2. **IP ro'yxatini bo'sh qoldiring** (Render bepul tarifida chiquvchi IP o'zgarib turadi). Bo'sh bo'lmasa, `403 ip_not_allowed` chiqadi.
3. (Ixtiyoriy, tezroq natija uchun) **Vebhuk** manzili: `https://vaynexo-q2ec.onrender.com/api/yupay/webhook`. Imzo kalit bilan tekshiriladi. Vebhuksiz ham ishlaydi: holat har 30 soniyada so'raladi.

## 2. Render → vaynexo → Environment
| Nomi | Qiymati |
|---|---|
| `DONATE_PROVIDER` | `yupay` |
| `DONATE_PROVIDER_KEY` | `ypk_…` kalit |
| `DONATE_BRAND_ML` | ixtiyoriy: Yupay brend slug (bo'sh bo'lsa avtomatik: `mobile-legends`) |
| `DONATE_BRAND_MC` | ixtiyoriy (avtomatik: `magic-chess…`) |
| `DONATE_LOW_BALANCE_USD` | ixtiyoriy, standart 20 |

## 3. Tekshirish
Mini App → Admin → **💎 Donat** → «🔌 Donat API» → **Ulanishni tekshirish**: depozit summasi chiqsa, ulandi.
Xatolar: 401 — kalit noto'g'ri; 403 — IP yoki hisob muzlatilgan.

## 4. Paketlarni bog'lash
Admin → **Donat paketlari** → paketni oching → **«Yupay katalogidan tanlash»** → nominalni tanlang (SKU UUID o'zi yoziladi).
SKU qo'lda yozilsa, katalogdagi `sku_id` bilan bir xil bo'lishi kerak. Bog'lanmagan paket buyurtmasi rad etilib, pul qaytariladi.

## 5. Qanday ishlaydi
- ID tekshiruvi: `POST /validate/player` (nik ko'rsatiladi). Tekshirib bo'lmasa — ruxsat beriladi, nik ko'rsatilmaydi.
- Buyurtma: `merchant_order_id = VX-D{id}` (idempotent: takroriy so'rov ikki marta yechmaydi).
- `delivered` → muvaffaqiyat; `paid/fulfilling/fulfillment_delayed` → kutiladi (qaytarish yo'q); `failed` + to'liq qaytarilgan → foydalanuvchiga pul qaytadi;
  `failed` + qisman → adminga «tekshiruv».
- Yupay ning o'zi rad etsa (depozit yetmadi, narx o'zgardi, nominal tugadi) → pul foydalanuvchiga qaytadi va adminga sabab bilan xabar keladi.
