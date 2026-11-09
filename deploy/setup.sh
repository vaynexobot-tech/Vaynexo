#!/usr/bin/env bash
# VAYNEXO — serverda bir marta ishga tushiriladi:  bash deploy/setup.sh
# Tokenni yashirin so'raydi, qolgan maxfiy kalitlarni o'zi yaratadi, .env yozadi va hammasini ishga tushiradi.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v docker >/dev/null || { echo "Docker o'rnatilmagan: curl -fsSL https://get.docker.com | sh"; exit 1; }
command -v openssl >/dev/null || { echo "openssl kerak: apt install -y openssl"; exit 1; }

if [ -f .env ]; then
  read -rp ".env allaqachon bor. Qayta yozilsinmi? (ha/yo'q): " ans
  [ "$ans" = "ha" ] || { echo "Mavjud .env bilan ishga tushiriladi."; SKIP_ENV=1; }
fi

if [ -z "${SKIP_ENV:-}" ]; then
  echo "=== Telegram ==="
  read -rsp "BOT_TOKEN (@BotFather dan, ekranda ko'rinmaydi): " BOT_TOKEN; echo
  [[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]] || { echo "Token formati noto'g'ri"; exit 1; }
  read -rp "Bot username (@ siz, masalan vaynexo_bot): " BOT_USERNAME
  read -rp "Domen (masalan app.vaynexo.uz): " DOMAIN
  read -rp "Admin Telegram ID (bir nechta bo'lsa vergul bilan): " ADMIN_IDS
  echo "=== P2P to'ldirish kartasi ==="
  read -rp "Karta raqami (8600 ...): " CARD
  read -rp "Karta egasi (ISM FAMILIYA): " HOLDER

  fernet_key=$(openssl rand -base64 32 | tr '+/' '-_')
  umask 077
  cat > .env <<EOF
BOT_TOKEN=$BOT_TOKEN
BOT_USERNAME=$BOT_USERNAME
DOMAIN=$DOMAIN
WEBAPP_URL=https://$DOMAIN
BOT_WEBHOOK_URL=https://$DOMAIN
BOT_WEBHOOK_SECRET=$(openssl rand -hex 24)
ADMIN_IDS=$ADMIN_IDS
ADMIN_CHAT_ID=0
BOOSTER_GROUP_ID=0
POSTGRES_PASSWORD=$(openssl rand -hex 24)
ENCRYPTION_KEY=$fernet_key
CORS_ORIGINS=https://$DOMAIN
P2P_CARD_NUMBER=$CARD
P2P_CARD_HOLDER=$HOLDER
P2P_SECRET=$(openssl rand -hex 24)
TOPUP_MIN=1000
TOPUP_MAX=20000000
TOPUP_TTL_MINUTES=30
COMMISSION_PERCENT=5
WITHDRAW_MIN=10000
ESCROW_AUTO_RELEASE_HOURS=48
REFERRAL_BONUS=0
STARS_RATE=220
DONATE_PROVIDER=mock
DONATE_PROVIDER_URL=
DONATE_PROVIDER_KEY=
DEV_MODE=false
EOF
  chmod 600 .env
  echo ".env yozildi (faqat root o'qiy oladi)."
  echo "MUHIM: .env faylining zaxira nusxasini xavfsiz joyda saqlang — ENCRYPTION_KEY yo'qolsa, saqlangan parollar o'qilmaydi."
fi

echo "=== Frontend yig'ilmoqda ==="
docker run --rm -v "$PWD/frontend":/app -w /app node:22-alpine sh -c "npm ci --no-audit --no-fund && npm run build"

echo "=== Konteynerlar ishga tushmoqda ==="
docker compose up -d --build

echo
echo "Tayyor. Tekshirish:  curl https://$(grep ^DOMAIN= .env | cut -d= -f2)/api/health"
echo "Loglar:             docker compose logs -f api worker"
echo "Keyin @BotFather → Bot Settings → Menu Button → https://$(grep ^DOMAIN= .env | cut -d= -f2)"
echo "SMS-forwarder uchun kalit (X-P2P-Secret):  grep P2P_SECRET .env"
