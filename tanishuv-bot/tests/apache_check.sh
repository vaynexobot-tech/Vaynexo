#!/bin/sh
# Haqiqiy Apache bilan .htaccess tekshiruvi (ixtiyoriy, root + apache2 kerak).
# Ishlatish: sh tests/apache_check.sh /yo‘l/domen_ildizi 8089
# Domen ildizida tanishuv-bot/ papkasi bo‘lishi kerak.
set -u
ROOT="$1"; PORT="${2:-8089}"
CONF=/tmp/tb_apache_test.conf
cat > "$CONF" <<C
Listen 127.0.0.1:$PORT
<VirtualHost 127.0.0.1:$PORT>
  DocumentRoot "$ROOT"
  <Directory "$ROOT">
    AllowOverride All
    Require all granted
  </Directory>
</VirtualHost>
C
a2enmod rewrite headers >/dev/null 2>&1
cp "$CONF" /etc/apache2/sites-enabled/zz-tb-test.conf
apache2ctl -k restart >/dev/null 2>&1 || apache2ctl start >/dev/null 2>&1
sleep 1
FAIL=0
chk() { code=$(curl -s -o /dev/null -w '%{http_code}' -X "$2" "http://127.0.0.1:$PORT$1"); if [ "$code" = "$3" ]; then echo "OK   $2 $1 -> $code"; else echo "FAIL $2 $1 -> $code (kutilgan $3)"; FAIL=1; fi; }
for p in /tanishuv-bot/src/Db.php /tanishuv-bot/src/ /tanishuv-bot/locales/uz.php /tanishuv-bot/sql/database.sql /tanishuv-bot/sql/migration.sql \
         /tanishuv-bot/docs/bank-contract.json /tanishuv-bot/tests/run.php /tanishuv-bot/storage/ /tanishuv-bot/config.php /tanishuv-bot/config.example.php \
         /tanishuv-bot/ORNATISH_UZ.txt /tanishuv-bot/docs/ORNATISH_BATAFSIL_UZ.txt /tanishuv-bot/sql/upgrade.sql /tanishuv-bot/src/Settings.php /tanishuv-bot/TEST_REPORT_UZ.txt /tanishuv-bot/database.sql /tanishuv-bot/.htaccess /tanishuv-bot/public/.htaccess; do
  chk "$p" GET 403
done
chk /tanishuv-bot/ GET 403
chk /tanishuv-bot/public/ GET 200
chk /tanishuv-bot/public/index.php GET 200
chk /tanishuv-bot/public/hmac-test.html GET 200
chk /tanishuv-bot/public/webhook.php GET 405
chk /tanishuv-bot/public/bank-webhook.php GET 405
rm -f /etc/apache2/sites-enabled/zz-tb-test.conf
apache2ctl -k stop >/dev/null 2>&1
exit $FAIL
