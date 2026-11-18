# Donat API ulash (Yupay yoki boshqa provayder)

Hozir donat QO'LDA bajariladi (`DONATE_PROVIDER=manual`). API ulangach avtomatik bo'ladi.

## 1. Render'ga kiritiladigan o'zgaruvchilar
Render → Dashboard → `vaynexo` servisi → **Environment**. Kalitni faqat shu yerga yozing, hech qayerga yubormang.

| O'zgaruvchi | Qiymat | Izoh |
|---|---|---|
| `DONATE_PROVIDER` | `http` | avtomatik rejim |
| `DONATE_PROVIDER_URL` | `https://...` | provayder API bazaviy manzili (hujjatdan) |
| `DONATE_PROVIDER_KEY` | kalit | provayder kabinetidan |
| `DONATE_AUTH_HEADER` | `Authorization` | hujjatda `X-API-Key` desa — shuni yozing |
| `DONATE_AUTH_PREFIX` | `Bearer ` | `X-API-Key` bo'lsa bo'sh qoldiring |
| `DONATE_CHECK_PATH` | `/player/check` | o'yinchi tekshirish yo'li |
| `DONATE_CREATE_PATH` | `/orders` | buyurtma yaratish yo'li |
| `DONATE_STATUS_PATH` | `/orders/{ref}` | holat yo'li (`{ref}` — bizning buyurtma raqami) |
| `DONATE_BALANCE_PATH` | `/balance` (ixtiyoriy) | «Ulanishni tekshirish» shuni so'raydi |

Saqlagach Render o'zi qayta ishga tushadi.

## 2. Tekshirish
Mini App → Admin → **💎 Donat** → tepadagi «🔌 Donat API» kartasi:
holat (yoqilgan/qo'lda), manzil, kalit o'rnatilganmi, **«Ulanishni tekshirish»** tugmasi
(401/403 — kalit noto'g'ri; 404 — yo'l noto'g'ri).

## 3. Provayder talab qiladigan JSON maydonlari
Hozirgi adapter (`backend/app/providers/http.py`) shu formatni kutadi:
- tekshirish: `POST {CHECK_PATH}` `{"game","user_id","zone_id"}` → `{"ok":true,"nickname":"..."}`
- buyurtma: `POST {CREATE_PATH}` `{"ref","product","game","user_id","zone_id"}` → `{"status":"success|pending|failed","id","message"}`
- holat: `GET {STATUS_PATH}` → `{"status","id"}`
Provayder hujjati boshqacha bo'lsa — hujjatni Claude'ga bering, maydon nomlarini moslab beradi.

## 4. Paketlar
Admin → Donat paketlari: har paketdagi **SKU** provayderning mahsulot kodiga teng bo'lishi shart (hujjatdan).

## 5. Qaytarish va xavfsizlik
- Provayder rad etsa — pul foydalanuvchi hamyoniga o'zi qaytadi.
- Javob kelmasa — buyurtma «tekshiruv»ga tushadi, admin «Bajarildi/Qaytarish» bosadi.
- Provayder hisobida balans bo'lishi shart. Kamayib qolsa buyurtmalar rad etiladi.
