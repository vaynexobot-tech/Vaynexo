# VAYNEXO — Telegram Mini App

Raqamli o'yin bozori: Mobile Legends / Magic Chess almaz donat, garantli akkaunt savdosi, rank boost,
Telegram Premium/Stars/Gift/NFT, turnirlar va Top 100.

| Qism | Texnologiya |
|---|---|
| Frontend (Mini App) | React 18 + TypeScript + Vite (`frontend/`) |
| API | Python 3.12, FastAPI, SQLAlchemy 2 (async) (`backend/app/api`) |
| Bot | aiogram 3 — webhook yoki polling (`backend/app/bot`) |
| Fon ishlari | arq + Redis — xabarlar, donat yetkazish, avto-tasdiq (`backend/app/worker.py`) |
| Baza | PostgreSQL 16 (Alembic migratsiyalari) |
| Server | Docker Compose + Caddy (avtomatik HTTPS) |

## 1. Botni tayyorlash (@BotFather)

1. `/newbot` → token oling.
2. `/mybots` → bot → **Bot Settings → Menu Button** → Mini App manzili: `https://SIZNING-DOMEN`.
3. `/newapp` (ixtiyoriy) — `t.me/bot/app` havolasi uchun.
4. Telegram ID'ingizni bilish uchun: botni ishga tushirgach `/id` yozing → `ADMIN_IDS` ga qo'ying.

## 2. Serverga o'rnatish (VPS, Ubuntu)

Kerak: domen (A-yozuvi server IP'siga), Docker.

```bash
git clone <repo> vaynexo && cd vaynexo
cp .env.example .env            # to'ldiring: BOT_TOKEN, DOMAIN, ADMIN_IDS, P2P_CARD_NUMBER ...
python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"   # -> ENCRYPTION_KEY
cd frontend && npm ci && npm run build && cd ..
docker compose up -d --build
```

Shundan so'ng botga `/start` yozing → «VAYNEXO ni ochish».
Migratsiyalar va boshlang'ich donat paketlari avtomatik qo'shiladi. Narx va **provayder SKU** larini Admin panel → Paketlar bo'limida to'g'rilang.

> `BOT_WEBHOOK_URL` to'ldirilsa bot webhook orqali API ichida ishlaydi (tavsiya etiladi), `bot` konteyneri o'zi to'xtaydi.
> Bo'sh bo'lsa — `bot` konteyneri polling rejimida ishlaydi.

## 3. Avto P2P to'ldirish

1. Foydalanuvchi summani kiritadi (50 000) → tizim **noyob** summa beradi (50 034), 30 daqiqa amal qiladi.
2. Foydalanuvchi aynan shu summani `P2P_CARD_NUMBER` kartasiga o'tkazadi.
3. Kartaga kirim xabari tizimga yetib keladi — **ikki yo'l**:
   - **SMS-forwarder** (Android telefon, karta SMS'lari keladigan): istalgan "SMS to webhook" ilovasi
     `POST https://DOMEN/api/p2p/incoming` ga yuboradi, sarlavha `X-P2P-Secret: <P2P_SECRET>`,
     tana: `{"text": "<SMS matni>", "external_id": "<sms id>"}`.
   - **Botga forward**: admin bank bildirishnomasini (Humo/Uzcard bot xabari) VAYNEXO botiga forward qiladi.
4. Summasi mos keladigan yagona so'rov topilsa — balans avtomatik to'ldiriladi.
   Topilmasa — adminga xabar boradi, Admin panel → Kirimlar bo'limidan qo'lda biriktiriladi.

Takroriy SMS ikki marta hisoblanmaydi. Kech to'lovlar (24 soatgacha) ham topiladi.

## 4. Donat provayderi

`backend/app/providers/http.py` — umumiy HTTP adapter. **Provayderingiz API hujjatiga moslab o'zgartirish kerak**
(fayl boshida kutilgan format yozilgan). So'ng `.env` da: `DONATE_PROVIDER=http`, `DONATE_PROVIDER_URL`, `DONATE_PROVIDER_KEY`.

Qoidalar:
- provayder aniq rad etsa → pul darhol hamyonga qaytadi, foydalanuvchi va admin xabardor;
- provayder javob bermasa (timeout) → avval holat so'raladi, 3 marta qayta uriniladi; baribir noma'lum bo'lsa
  buyurtma **«Tekshiruv»** ga tushadi va admin «Bajarildi» yoki «Qaytarish» ni bosadi
  (aks holda ham almaz, ham pul berib yuborilishi mumkin).

`DONATE_PROVIDER=mock` — sinov rejimi: ID `0` bilan boshlansa rad etadi, `9` bilan boshlansa javob bermaydi.

## 5. Ixtiyoriy sozlamalar

- `BOOSTER_GROUP_ID` — boosterlar yopiq guruhi. Botni guruhga qo'shing, `/id` yozing. Yangi boost buyurtmalar
  guruhga «Qabul qilish» tugmasi bilan tushadi; booster ma'lumotlarni shaxsiy xabarda oladi
  (boosterlar avval botga `/start` yozgan bo'lishi kerak). Booster ulushi — 70% (`services.py: BOOSTER_SHARE_PERCENT`).
- `ADMIN_CHAT_ID` — ogohlantirishlar alohida guruhga borsin desangiz.
- `REFERRAL_BONUS` — do'sti birinchi marta to'ldirganda taklif qilgan odamga bonus.
- TG xizmatlar va boost narxlari: `backend/app/services/catalog.py`.

## 6. Lokal ishlab chiqish

```bash
# backend (PostgreSQL va Redis kerak)
python -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements-dev.txt
cd backend
export DATABASE_URL=postgresql+asyncpg://postgres@localhost/vaynexo DEV_MODE=true ADMIN_IDS=1 BOT_TOKEN=123:x ENCRYPTION_KEY=...
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload       # API
python -m app.worker                # fon ishlari
python -m app.bot                   # bot (polling)
pytest                              # testlar (vaynexo_test bazasi kerak)

# frontend
cd frontend && npm install && npm run dev
# brauzerda Telegramsiz: http://localhost:5173/?dev=1   (DEV_MODE=true bo'lganda; 1 = admin)
```

**Diqqat:** ishlab chiqarishda `DEV_MODE=false` bo'lishi shart — aks holda istalgan odam o'zini boshqa foydalanuvchi qilib ko'rsata oladi.

## 7. Yuklama (30–40 ming foydalanuvchi)

- API 4 ta uvicorn worker bilan ishlaydi; frontend va media fayllarni Caddy to'g'ridan-to'g'ri beradi (CDN keshi bilan).
- Og'ir ishlar (Telegram xabarlari, provayder so'rovlari) navbatda — foydalanuvchi kutmaydi.
- Pul bilan bog'liq har bir amal: qatorni bloklash (`FOR UPDATE`) + noyob `idem_key` — parallel so'rovlarda ham
  ikki marta yechilmaydi (testlar bilan tekshirilgan).
- Ro'yxatlar sahifalab yuklanadi, Top 100 va paketlar Redis'da keshlanadi, rate-limit bor.
- Boshlash uchun 1 ta VPS (4 vCPU / 8 GB) yetarli. O'sganda: PostgreSQL'ni alohida (managed) serverga, media'ni S3/R2 ga ko'chiring.
