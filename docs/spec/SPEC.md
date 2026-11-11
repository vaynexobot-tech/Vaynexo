# VAYNEXO — texnik topshiriq

## 1. Umumiy

- **Foydalanuvchilar:** O‘zbekistondagi MLBB va Magic Chess o‘yinchilari.
- **Kirish nuqtalari:**
  - Telegram bot `@vaynexobot` → "Ochish" tugmasi → Mini App.
  - Botdagi yashirin buyruqlar: `/administ` (admin), `/booster` (booster).
  - Admin panel (veb, kompyuter va mobil).
- **Valyuta:** so‘m. Hamma summalar butun son.
- **Tillar:** o‘zbek (asosiy), keyin rus.

### Rollar

| Rol | Imkoniyatlar |
|---|---|
| user | Xarid, ijara, Boost, TG xizmat, donat, Arena, Hamkor, e’lon joylash (KYC bilan) |
| seller | user + akkaunt sotish/ijaraga berish (KYC majburiy) |
| booster | Boost buyurtmalarini qabul qilish va progress yuborish (`/booster`, "VAYNEXO boosterlar" guruhi) |
| operator | Murojaatlar, to‘lov tekshiruvi, moderatsiya |
| admin | Hammasi + sozlamalar, rollar, buxgalteriya |

## 2. Modullar va biznes qoidalari

### 2.1 Autentifikatsiya
- Mini App `initData` → `POST /auth/telegram` → serverda HMAC tekshiruvi → JWT (qisqa muddatli) + refresh.
- Birinchi kirishda `users` yozuvi yaratiladi. `/start <kod>` bo‘lsa, taklif (referral) kodi saqlanadi.

### 2.2 Hamyon (Wallet)
- Balans `wallet_transactions` ledger orqali hisoblanadi: `topup`, `purchase`, `escrow_hold`, `escrow_release`, `refund`, `reward`, `fee`, `adjustment`.
- **To‘ldirish — kartaga o‘tkazma (P2P), 1-bosqich:**
  1. Foydalanuvchi summa (1 000 – limit) va usulni tanlaydi.
  2. Server noyob summa beradi: `summa + random(1..99)`. Ochiq so‘rovlar orasida takrorlanmasin.
  3. Faol kartalardan biri ko‘rsatiladi (navbat bilan) yoki hammasi ro‘yxat bo‘lib chiqadi (dizaynda 3 ta karta).
  4. Taymer `timeout_minutes` (10). Vaqt tugasa — `expired`.
  5. "To‘ladim" → holat `checking`. Ixtiyoriy chek rasmi biriktiriladi.
  6. Tasdiqlash: admin/operator "Vazifalar"da tasdiqlaydi (MVP). Keyinroq bank SMS yoki API orqali avtomatik.
  7. Tasdiqlangach balans to‘ldiriladi va bot xabar yuboradi.
- **Keyingi bosqich:** Payme, Click, Paynet merchant API (to‘g‘ridan-to‘g‘ri to‘lov), webhook’lar idempotent.
- Daraja limitlari: Silver — bir martalik 500 000 (sozlanadi).

### 2.3 Account savdo (Marketplace) + Garant (escrow)
- **E’lon:** o‘yin, kolleksiya darajasi (7 ta: World → Junior), rank, skin soni, qahramonlar soni, sarlavha, tavsif, narx, media (rasm/video).
  - Muqova majburiy: sotuvchi media ichidan bittasini tanlaydi (videodan kadr olinadi).
  - Akkaunt login ma’lumotlari shifrlab saqlanadi.
- **Moderatsiya:** yangi e’lon `moderation` holatida, admin tasdiqlagach `active`.
- **VIP:** kunlik narx × kunlar (1/3/7/14). VIP e’lon ro‘yxat tepasida, sariq ramkada turadi.
- **Filtrlar:** kolleksiya darajasi; saralash: eng yangi, arzon, qimmat, reyting; matn bo‘yicha qidiruv.
- **Xarid (Garant):**
  1. KYC majburiy (sozlamaga qarab).
  2. Foydalanuvchi kelishuviga rozilik.
  3. Balansdan yechiladi → `escrow_hold`.
  4. Xaridorga akkaunt ma’lumotlari ochiladi.
  5. Xaridor "Tasdiqlash" bosadi → `escrow_release` (sotuvchiga, xizmat haqi ayirilib). Javob bo‘lmasa, `escrow_release_days` dan keyin avtomatik.
  6. "Muammo bor" → nizo (`dispute`), admin hal qiladi: `refund` yoki `release`.
- E’lon holatlari: `draft → moderation → active → reserved → sold | archived | rejected`.

### 2.4 Account ijara
- Muddatlar: 12 soat, 24 soat, 3 kun, 1 hafta. Narx = soatlik narx × soat − chegirma (fixed yoki %).
- Depozit: fixed yoki akkaunt qiymatining foizi. Muddat tugagach, egasi tasdiqlasa qaytariladi.
- KYC majburiy (ijaraga olish va berish uchun).
- Shartnomaga rozilik majburiy.
- Holatlar: `pending_payment → active → returning → completed | disputed`.
- Band akkauntda "bo‘shaydi: HH:MM" ko‘rsatiladi.
- Qoida buzilsa (parol yoki pochtani almashtirish), depozit ushlab qolinadi va foydalanuvchi bloklanadi.

### 2.5 Boost
- Rank pozitsiyasi: Epic V..I (0–24), Legend V..I (25–49), Mythic N★ (50+N). Mythic 50★+ = Mythical Glory.
- Narx = har bir yulduz uchun daraja narxlari yig‘indisi (`star_price_by_tier`).
- Qo‘shimchalar (foiz yoki fixed):
  - **Express** — muddatni qisqartiradi.
  - **Qo‘shimcha:** "Qahramon tanlash" (nomi yoziladi) va/yoki "Liniya tanlash" (Gold, Mid, EXP, Jungle, Roam). Ikkalasi birga bo‘lsa, foizlar qo‘shiladi. Faqat MLBB uchun.
- Izoh booster uchun (ixtiyoriy). Kirish usuli: Moonton ID / Google.
- **Oqim:** buyurtma → to‘lov (escrow) → boosterlar guruhiga e’lon → booster "Qabul qilish" → progress yangilanishlari (bot orqali mijozga) → "Tugadi" → mijoz tasdiqlaydi yoki "Muammo bor" → release/dispute.
- Booster ulushi: sozlanadigan foiz. Booster shaxsi mijozga ko‘rsatilmaydi, aloqa faqat bot orqali.

### 2.6 TG xizmatlar
- **Premium:** 1, 3, 6, 12 oy; oylik narx va tejash foizi avtomatik hisoblanadi.
- **Stars:** paketlar va bonus, yoki ixtiyoriy miqdor (≥ min) × Star narxi.
- **Gift:** sovg‘alar ro‘yxati, qabul qiluvchi, xabar, anonim yuborish.
- **Kimga:** o‘zimga yoki @username (format tekshiruvi; mavjudligini tekshirish keyinroq).
- Bajarish: operator qo‘lda (MVP). Holatlar `paid → in_progress → delivered | failed`. Failed bo‘lsa, avtomatik refund.

### 2.7 Olmos donat (MLBB / Magic Chess)
- 4 qadam: o‘yinchi ID + Zone ID → paket → to‘lov → tasdiq.
- Bajarish: operator yoki ta’minotchi API (keyinroq). Paketlar va narxlar admin panelda.

### 2.8 KYC
- Hujjatlar: hujjat bilan selfi, pasport oldi, pasport orqasi.
- Holatlar: `none → pending → approved | rejected` (rad etish sababi bilan).
- Qaysi modullarda majburiyligi `kyc.required_for` da sozlanadi.
- Majburiy joyda KYC bo‘lmasa, amal bloklanadi va Verifikatsiya ekrani ochiladi. Tasdiqlangach, foydalanuvchi o‘sha ekranga qaytadi.

### 2.9 Hamkor dasturi
- Foydalanuvchi TikTok, Instagram yoki YouTube video havolasini yuboradi (domen tekshiriladi, takror havola qabul qilinmaydi).
- Limit: bir kishi `video_interval_days` (2) kunda 1 ta video.
- Ko‘rishlar `count_days` (10) kundan keyin hisoblanadi.
- Talablar:
  - kamida `min_views` (3 000) ko‘rish;
  - layk/ko‘rish nisbati ≥ 3%;
  - #vaynexo, #vaynexobot, @vaynexobot belgisi;
  - akkaunt kamida 1 oylik.
- Statistika skrinshoti so‘ralishi mumkin.
- Mukofot darajalari: 3k / 10k / 25k / 50k. 50k dan yuqori — shaxsiy shartnoma (admin bilan bog‘lanish).
- Admin "Vazifalar"da tasdiqlaydi yoki rad etadi. Mukofot avtomatik beriladi: VIP krediti, turnir pass, olmos buyurtmasi, nishon.

### 2.10 Arena
- **Turnirlar:** holatlar `soon` (eslatma) → `registration` → `live` → `finished`. Ro‘yxatdan o‘tish (jamoa yoki yakka), qoidalarga rozilik, kirish to‘lovi yoki pass. Natijalarni admin kiritadi. Sovrin fondi.
- **Bepul prognoz:** match uchun tanlov; to‘g‘ri bo‘lsa `correct_prediction` ball beriladi. Pul yo‘q.
- **Jamoa topish:** e’lonlar (rol, rank, onlayn vaqt, izoh, o‘yinchi yoki jamoa), 7 kun yashaydi. "Yozish" — bot orqali bog‘lanish.
- **Reyting:** sezon (`season_days`), ball yig‘indisi, Top 100, sezon mukofotlari.
- **Vazifalar:** kunlik va haftalik progress, "Olish" → ball.
- **Ballni almashtirish:** Boost chegirmasi, VIP 3 kun, turnirga bepul kirish.
- Ball `points_ledger` da saqlanadi. Pulga almashtirilmaydi.

### 2.11 Bildirishnomalar (bot)
To‘lov holati, buyurtma holatlari, Boost progress, KYC natijasi, e’lon moderatsiyasi, Hamkor natijasi, turnir eslatmasi, nizo javoblari.

### 2.12 Admin panel
- Dizayn: `design/VAYNEXO-Admin-panel.html`.
- **Bo‘limlar:**
  - Boshqaruv paneli
  - Akkaunt e’lonlari (moderatsiya)
  - Garant bitimlari va nizolar
  - Ijara
  - Boost buyurtmalari
  - TG xizmatlar
  - To‘lovlar va hamyonlar
  - Narxlar / kurslar / xizmat haqi (barcha `SETTINGS.json`)
  - Turnirlar
  - Top 100
  - Foydalanuvchilar va rollar
  - KYC
  - Chat va shikoyatlar
  - Bannerlar va matnlar
  - FAQ
  - Bildirishnomalar
  - Bot boshqaruvi (`/administ`)
  - Adminlar va rollar
  - Amallar jurnali
- **Mobil:** Asosiy, Vazifalar (to‘lov cheki, e’lon, KYC, Hamkor video, murojaat — "Tasdiqlash / Rad etish"), Narxlar, Menyu, API ulanishlar, Buxgalteriya, Texnik ishlar, Adminlar, Taklif kodi.
- Har bir pullik sozlama yonida "so‘m / %" tanlovi bor.
- "Saqlash" bosilganda `settings` yangilanadi va `settings_version` oshadi. Mini App yangi qiymatlarni keshdan yangilaydi.

## 3. Ma’lumotlar bazasi (asosiy jadvallar)

`users` (tg_id, username, role, level, kyc_status, referral_code, referred_by, blocked) ·
`wallet_transactions` (user_id, type, amount, ref_type, ref_id, idempotency_key, created_at) ·
`topup_requests` (user_id, method, amount, unique_amount, card_id, status, receipt_file, expires_at, confirmed_by) ·
`payment_cards` (number_enc, holder, type, active, order) ·
`listings` (seller_id, game, collector_level, rank, skins, heroes, title, description, price, cover_media_id, vip_until, status, credentials_enc) ·
`listing_media` ·
`escrow_deals` (listing_id, buyer_id, seller_id, amount, fee, status, release_at) ·
`disputes` ·
`rentals` (listing_id, renter_id, hours, price, discount, deposit, status, starts_at, ends_at) ·
`boost_orders` (user_id, game, from_pos, to_pos, stars, express, hero_name, lane, note, login_method, price, booster_id, status) ·
`boost_updates` ·
`tg_orders` (type, plan/qty/gift, recipient, anonymous, message, price, status) ·
`diamond_orders` ·
`kyc_submissions` (user_id, files_enc, status, reviewer_id, reason) ·
`partner_videos` (user_id, platform, url, submitted_at, views, likes, status, tier, reward_ref) ·
`tournaments` · `tournament_entries` · `matches` · `predictions` ·
`team_posts` ·
`seasons` · `points_ledger` (user_id, amount, reason, ref) · `missions_progress` · `point_exchanges` ·
`notifications` ·
`settings` (key, value_json, version) ·
`audit_log` (admin_id, action, entity, before, after, at).

## 4. API (namuna)

```
POST /auth/telegram
GET  /me                         PATCH /me
GET  /settings/public
GET  /wallet                     GET /wallet/transactions
POST /wallet/topup               POST /wallet/topup/:id/paid   POST /wallet/topup/:id/receipt
GET  /listings?level=&sort=&q=   GET /listings/:id    POST /listings   POST /listings/:id/vip
POST /deals                      POST /deals/:id/confirm      POST /deals/:id/dispute
GET  /rentals/listings           POST /rentals                POST /rentals/:id/return
POST /boost/quote                POST /boost/orders           GET /boost/orders/:id
POST /tg/orders                  POST /diamonds/orders
POST /kyc                        GET /kyc
POST /partner/videos             GET /partner/videos
GET  /arena/tournaments          POST /arena/tournaments/:id/join
POST /arena/predictions          GET/POST /arena/team-posts
GET  /arena/leaderboard          GET /arena/missions   POST /arena/missions/:key/claim   POST /arena/exchange
Admin: /admin/* (rol tekshiruvi, audit log)
```

Narx hisoblash (`/boost/quote`, ijara, VIP, Premium oylik narxi) `packages/shared` da bitta funksiya sifatida yoziladi; frontend faqat ko‘rsatadi, server qayta hisoblaydi.

## 5. Bot

- `/start` — salom, "Ochish" (WebApp tugmasi), taklif kodi.
- `/help` — yordam va @VaynexoSupport.
- `/administ` — faqat admin: tezkor vazifalar, statistika, "Admin panelni ochish".
- `/booster` — faqat booster: yangi buyurtmalar, "Qabul qilish", progress yuborish.
- Boosterlar guruhi: yangi Boost buyurtmalari kartochka bo‘lib tushadi (dizayn: "VAYNEXO boosterlar").
- Mijozga holat xabarlari (dizayn: "Mijoz holat xabarlari").

## 6. Xavfsizlik va qonun

- HTTPS, CORS faqat Mini App domeni, rate limit (auth, topup, partner).
- Shifrlash (AES-GCM, kalit `.env`da): akkaunt login/parollari, KYC fayllari, karta raqamlari.
- Shaxsiy ma’lumotlar: O‘zbekiston qonunchiligi fuqarolar ma’lumotlarini O‘zbekistondagi serverda saqlashni talab qilishi mumkin — VPS joylashuvini egasi tekshiradi.
- P2P (shaxsiy kartaga) to‘lov qabul qilish va escrow — yuridik maslahat talab qiladi. Kod buni sozlama orqali o‘chirib qo‘yish imkonini bersin.
- MLBB foydalanish shartlari akkaunt savdosi, ijarasi va boost’ni cheklashi mumkin — bu egasining qarori, kodga ta’sir qilmaydi.

## 7. Bosqichlar

1. **MVP:**
   - Auth
   - Hamyon (P2P + admin tasdiqlashi)
   - TG xizmatlar
   - Boost (to‘liq oqim + boosterlar)
   - Admin: Narxlar, Vazifalar, Foydalanuvchilar
   - Bot: /start, /administ, /booster, bildirishnomalar
2. **Savdo:**
   - KYC
   - Account savdo + Garant + nizolar
   - VIP
   - Mening e’lonlarim
   - Xaridlar tarixi
3. **Ijara va Olmos donat.**
4. **Arena:**
   - Turnirlar
   - Prognoz
   - Jamoa
   - Reyting
   - Vazifalar
   - Ball almashtirish
5. **Hamkor dasturi.**
6. **To‘lov provayderlari:** Payme, Click, Paynet API; rus tili.

Har bir bosqich oxirida:
- seed ma’lumotlar bilan ishlaydigan demo;
- testlar o‘tgan bo‘lsin;
- `README` yangilangan bo‘lsin.
