#!/usr/bin/env bash
# alwaysdata "User program" sayti shu buyruqni ishga tushiradi. $IP va $PORT ni alwaysdata o'zi beradi.
# Yengil rejimda faqat BITTA uvicorn jarayoni bo'lishi shart (fon ishlari shu jarayon ichida).
cd "$(dirname "$0")/../backend" || exit 1
exec "$HOME/vaynexo-venv/bin/uvicorn" app.main:app \
  --host "${IP:-0.0.0.0}" --port "${PORT:-8100}" \
  --workers 1 --proxy-headers --forwarded-allow-ips='*'
