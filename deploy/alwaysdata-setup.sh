#!/usr/bin/env bash
# VAYNEXO — alwaysdata'ga o'rnatish (yengil rejim: Redis'siz, bitta jarayon).
# SSH orqali kirib:  bash ~/vaynexo/deploy/alwaysdata-setup.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$HOME/vaynexo-venv"
ACC="${USER:-$(whoami)}"

echo "=== VAYNEXO · alwaysdata o'rnatish (akkaunt: $ACC) ==="
command -v python3 >/dev/null || { echo "python3 topilmadi. Admin panel → Environment → Python versiyasini tanlang."; exit 1; }
command -v npm >/dev/null || { echo "npm topilmadi. Admin panel → Environment → Node.js versiyasini tanlang."; exit 1; }

ENV_FILE="$ROOT/backend/.env"
if [ -f "$ENV_FILE" ]; then
  read -rp "backend/.env allaqachon bor. Qayta yozilsinmi? (ha/yo'q): " ans
  [ "$ans" = "ha" ] || SKIP_ENV=1
fi

if [ -z "${SKIP_ENV:-}" ]; then
  echo "--- Telegram ---"
  read -rsp "BOT_TOKEN (ekranda ko'rinmaydi): " BOT_TOKEN; echo
  [[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]] || { echo "Token formati noto'g'ri"; exit 1; }
  read -rp "Bot username (@ siz): " BOT_USERNAME
  read -rp "Admin Telegram ID (vergul bilan): " ADMIN_IDS
  read -rp "Sayt manzili [$ACC.alwaysdata.net]: " DOMAIN; DOMAIN="${DOMAIN:-$ACC.alwaysdata.net}"
  echo "--- PostgreSQL (admin panel → Databases → PostgreSQL) ---"
  read -rp "Baza nomi [${ACC}_vaynexo]: " DB_NAME; DB_NAME="${DB_NAME:-${ACC}_vaynexo}"
  read -rp "Baza foydalanuvchisi [$ACC]: " DB_USER; DB_USER="${DB_USER:-$ACC}"
  read -rsp "Baza paroli (ko'rinmaydi): " DB_PASS; echo
  read -rp "Baza serveri [postgresql-$ACC.alwaysdata.net]: " DB_HOST; DB_HOST="${DB_HOST:-postgresql-$ACC.alwaysdata.net}"
  echo "--- P2P karta ---"
  read -rp "Karta raqami: " CARD
  read -rp "Karta egasi: " HOLDER

  rnd() { python3 -c "import secrets;print(secrets.token_hex(24))"; }
  DB_URL=$(DB_USER="$DB_USER" DB_PASS="$DB_PASS" DB_HOST="$DB_HOST" DB_NAME="$DB_NAME" python3 -c \
    "import os,urllib.parse as u;print('postgresql+asyncpg://%s:%s@%s/%s'%(u.quote(os.environ['DB_USER'],safe=''),u.quote(os.environ['DB_PASS'],safe=''),os.environ['DB_HOST'],os.environ['DB_NAME']))")
  FERNET=$(python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
  umask 077
  cat > "$ENV_FILE" <<EOF
BOT_TOKEN=$BOT_TOKEN
BOT_USERNAME=$BOT_USERNAME
WEBAPP_URL=https://$DOMAIN
BOT_WEBHOOK_URL=https://$DOMAIN
BOT_WEBHOOK_SECRET=$(rnd)
ADMIN_IDS=$ADMIN_IDS
ADMIN_CHAT_ID=0
BOOSTER_GROUP_ID=0
DATABASE_URL=$DB_URL
REDIS_URL=
FRONTEND_DIR=$ROOT/frontend/dist
MEDIA_DIR=$ROOT/backend/media
ENCRYPTION_KEY=$FERNET
CORS_ORIGINS=https://$DOMAIN
P2P_CARD_NUMBER=$CARD
P2P_CARD_HOLDER=$HOLDER
P2P_SECRET=$(rnd)
COMMISSION_PERCENT=5
WITHDRAW_MIN=10000
ESCROW_AUTO_RELEASE_HOURS=48
REFERRAL_BONUS=0
DONATE_PROVIDER=mock
DEV_MODE=false
EOF
  chmod 600 "$ENV_FILE"
  echo "backend/.env yozildi. Zaxira nusxasini xavfsiz joyda saqlang (ENCRYPTION_KEY!)."
fi

echo "=== Python kutubxonalari (2-4 daqiqa) ==="
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$ROOT/backend/requirements.txt"

echo "=== Frontend yig'ilmoqda ==="
(cd "$ROOT/frontend" && npm ci --no-audit --no-fund --loglevel=error && npm run build >/dev/null)

echo "=== Baza jadvallari ==="
(cd "$ROOT/backend" && "$VENV/bin/alembic" upgrade head && "$VENV/bin/python" -m app.seed)

chmod +x "$ROOT/deploy/alwaysdata-start.sh"
echo
echo "TAYYOR. Endi admin panel → Web → Sites → Add a site:"
echo "  Addresses:          $(grep ^WEBAPP_URL= "$ENV_FILE" | cut -d/ -f3)"
echo "  Type:               User program"
echo "  Command:            $ROOT/deploy/alwaysdata-start.sh"
echo "  Working directory:  $ROOT/backend"
echo "Saqlagach 1 daqiqa kuting va botga /start yozing."
