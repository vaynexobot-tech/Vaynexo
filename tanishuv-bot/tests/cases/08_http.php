<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Bank;
use TB\Setup;

final class Http
{
    public static array $procs = [];

    public static function freePort(): int
    {
        $s = stream_socket_server('tcp://127.0.0.1:0');
        $name = stream_socket_get_name($s, false);
        fclose($s);
        return (int)substr($name, strrpos($name, ':') + 1);
    }

    public static function serve(array $args, array $env): int
    {
        $port = self::freePort();
        $cmd = array_merge([PHP_BINARY, '-S', '127.0.0.1:' . $port], $args);
        $p = proc_open($cmd, [0 => ['file', '/dev/null', 'r'], 1 => ['file', '/dev/null', 'w'], 2 => ['file', '/dev/null', 'w']], $pipes, TB_ROOT, array_merge(getenv(), $env));
        self::$procs[] = $p;
        for ($i = 0; $i < 100; $i++) {
            $c = @fsockopen('127.0.0.1', $port, $e1, $e2, 0.1);
            if ($c) {
                fclose($c);
                break;
            }
            usleep(50000);
        }
        return $port;
    }

    public static function stop(): void
    {
        foreach (self::$procs as $p) {
            proc_terminate($p);
            proc_close($p);
        }
        self::$procs = [];
    }

    /** @return array{0:int,1:string,2:array} */
    public static function req(string $method, string $url, ?string $body = null, array $headers = []): array
    {
        $ch = curl_init($url);
        $respHeaders = [];
        curl_setopt_array($ch, [
            CURLOPT_CUSTOMREQUEST => $method,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_TIMEOUT => 30,
            CURLOPT_HEADERFUNCTION => function ($ch, $h) use (&$respHeaders) {
                $respHeaders[] = trim($h);
                return strlen($h);
            },
        ]);
        if ($body !== null) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
        }
        $out = (string)curl_exec($ch);
        $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        curl_close($ch);
        return [$code, $out, $respHeaders];
    }
}

$t('http: webhook, cron, bank endpointlari (metod, secret, JSON, body limit, kalit, imzo)', function () {
    $log = tempnam(sys_get_temp_dir(), 'mocktg');
    $tgPort = Http::serve([TB_ROOT . '/tests/mock_tg_server.php'], ['MOCK_LOG' => $log]);
    $cfg = T::$cfg;
    $cfg['telegram_api_base'] = 'http://127.0.0.1:' . $tgPort;
    $cfgFile = T::writeConfig($cfg, sys_get_temp_dir() . '/tb_http_cfg_' . T::$dbName . '.php');
    T::$cfgFile = sys_get_temp_dir() . '/tb_test_config_' . T::$dbName . '.php';
    $port = Http::serve(['-t', TB_ROOT . '/public'], ['TB_CONFIG' => $cfgFile]);
    $base = 'http://127.0.0.1:' . $port;
    $sec = 'X-Telegram-Bot-Api-Secret-Token: ' . $cfg['webhook_secret'];
    try {
        // Webhook: faqat POST
        foreach (['GET', 'PUT', 'DELETE'] as $m) {
            [$c, , $h] = Http::req($m, "$base/webhook.php");
            T::eq($c, 405, "webhook $m → 405");
        }
        $upd = json_encode(T::msgUpdate(8001, ['text' => '/start']));
        [$c] = Http::req('POST', "$base/webhook.php", $upd, ['Content-Type: application/json']);
        T::eq($c, 403, 'secret yo‘q → 403');
        [$c] = Http::req('POST', "$base/webhook.php", $upd, ['Content-Type: application/json', 'X-Telegram-Bot-Api-Secret-Token: wrong']);
        T::eq($c, 403, 'noto‘g‘ri secret → 403');
        [$c] = Http::req('POST', "$base/webhook.php", '{not json', ['Content-Type: application/json', $sec]);
        T::eq($c, 400, 'invalid JSON → 400');
        [$c] = Http::req('POST', "$base/webhook.php", '[1,2]', ['Content-Type: application/json', $sec]);
        T::eq($c, 400, 'update_id siz JSON → 400');
        $big = json_encode(['update_id' => 1, 'pad' => str_repeat('a', 1048576)]);
        [$c] = Http::req('POST', "$base/webhook.php", $big, ['Content-Type: application/json', $sec]);
        T::eq($c, 413, 'body > 1 MiB → 413');
        [$c, $out] = Http::req('POST', "$base/webhook.php", $upd, ['Content-Type: application/json', $sec]);
        T::eq([$c, $out], [200, '{"ok":true}'], 'to‘g‘ri update → 200');
        T::eq((int)App::db()->val('SELECT COUNT(*) FROM tb_processed_updates WHERE update_id = ?', [json_decode($upd, true)['update_id']]), 1, 'update qayd etildi');
        [$c] = Http::req('POST', "$base/webhook.php", $upd, ['Content-Type: application/json', $sec]);
        T::eq($c, 200, 'takroriy update → 200 (no-op)');
        $lines = array_filter(explode("\n", (string)file_get_contents($log)));
        $methods = array_map(fn($l) => json_decode($l, true)['method'], $lines);
        T::ok(in_array('sendMessage', $methods, true), 'webhookdan keyin outbox CurlTransport orqali yuborildi');
        // Guruh chatidagi xabar e’tiborsiz
        $grp = T::msgUpdate(8002, ['text' => '/start']);
        $grp['message']['chat'] = ['id' => -100123, 'type' => 'supergroup'];
        [$c] = Http::req('POST', "$base/webhook.php", json_encode($grp), [$sec]);
        T::eq($c, 200, 'guruh update → 200');
        T::eq(T::user(8002), null, 'guruh xabari qayta ishlanmadi');
        $mis = T::msgUpdate(8003, ['text' => '/start']);
        $mis['message']['chat']['id'] = 8004;
        Http::req('POST', "$base/webhook.php", json_encode($mis), [$sec]);
        T::eq(T::user(8003), null, 'chat.id ≠ from.id e’tiborsiz');

        // CRON
        [$c] = Http::req('GET', "$base/cron.php");
        T::eq($c, 403, 'cron kalitsiz → 403');
        [$c] = Http::req('GET', "$base/cron.php?key=wrong");
        T::eq($c, 403, 'cron noto‘g‘ri kalit → 403');
        [$c] = Http::req('GET', "$base/cron.php?key=" . $cfg['webhook_secret']);
        T::eq($c, 403, 'webhook_secret cron kaliti sifatida ishlamaydi');
        [$c, $out] = Http::req('GET', "$base/cron.php?key=" . $cfg['cron_key']);
        T::eq($c, 200, 'cron GET kalit → 200');
        T::ok(isset(json_decode($out, true)['sent']), 'cron JSON statistikasi');
        T::ok(!str_contains($out, $cfg['cron_key']), 'javobda kalit yo‘q');
        [$c] = Http::req('POST', "$base/cron.php", '', ['X-Cron-Key: ' . $cfg['cron_key']]);
        T::eq($c, 200, 'cron X-Cron-Key sarlavha → 200');
        [$c] = Http::req('PUT', "$base/cron.php?key=" . $cfg['cron_key']);
        T::eq($c, 405, 'cron PUT → 405');

        // Bank
        [$c] = Http::req('GET', "$base/bank-webhook.php");
        T::eq($c, 405, 'bank GET → 405');
        $raw = json_encode(['source' => 'sms_gateway', 'event_id' => 'http-1', 'test' => true, 'amount_minor' => 100, 'currency' => 'UZS', 'card_last4' => '1234']);
        [$c] = Http::req('POST', "$base/bank-webhook.php", $raw, ['Content-Type: application/json']);
        T::eq($c, 401, 'bank imzosiz → 401');
        $ts = (string)time();
        $sig = Bank::sign($cfg['bank']['hmac_secret'], $ts, $raw);
        [$c, $out] = Http::req('POST', "$base/bank-webhook.php", $raw, ['Content-Type: application/json', 'X-Bank-Timestamp: ' . $ts, 'X-Bank-Signature: ' . $sig]);
        T::eq($c, 200, 'bank imzo bilan test event → 200');
        T::eq(json_decode($out, true)['test'] ?? null, true, 'test=true javobi');
        [$c] = Http::req('POST', "$base/bank-webhook.php", str_repeat('x', 32769), ['X-Bank-Timestamp: ' . $ts, 'X-Bank-Signature: ' . $sig]);
        T::eq($c, 413, 'bank body > 32 KiB → 413');

        // Setup HTTP da ishlamaydi
        [$c, $out] = Http::req('GET', "$base/setup.php");
        T::eq($c, 403, 'setup.php HTTP da → 403');
        T::ok(!str_contains($out, $cfg['setup_key']) && !str_contains($out, 'TEST_TOKEN'), 'setup javobida maxfiy qiymat yo‘q');

        // Hech bir javobda token/parol yo‘q
        foreach ($lines as $l) {
            T::ok(!str_contains($l, 'TEST_TOKEN_NOT_REAL'), 'mock log body da token yo‘q');
        }
    } finally {
        Http::stop();
        @unlink($cfgFile);
        @unlink($log);
    }
});

$t('http: setup.php (HTTPS, setup_key, CSRF, getMe, getWebhookInfo, setWebhook, yopish)', function () {
    T::ok(Setup::isHttps(['HTTPS' => 'on']), 'HTTPS=on');
    T::ok(Setup::isHttps(['SERVER_PORT' => '443']), 'port 443');
    T::ok(!Setup::isHttps(['HTTPS' => 'off', 'SERVER_PORT' => '80']), 'HTTP rad');
    T::ok(!Setup::isHttps(['HTTP_X_FORWARDED_PROTO' => 'https']), 'X-Forwarded-Proto ga sukut bo‘yicha ishonilmaydi');

    $log = tempnam(sys_get_temp_dir(), 'mocktg');
    $tgPort = Http::serve([TB_ROOT . '/tests/mock_tg_server.php'], ['MOCK_LOG' => $log]);
    $cfg = T::$cfg;
    $cfg['telegram_api_base'] = 'http://127.0.0.1:' . $tgPort;
    $cfgFile = T::writeConfig($cfg, sys_get_temp_dir() . '/tb_https_cfg_' . T::$dbName . '.php');
    T::$cfgFile = sys_get_temp_dir() . '/tb_test_config_' . T::$dbName . '.php';
    $port = Http::serve([TB_ROOT . '/tests/https_router.php'], ['TB_CONFIG' => $cfgFile]);
    $base = 'http://127.0.0.1:' . $port;
    try {
        [$c, $out] = Http::req('GET', "$base/setup.php");
        T::eq($c, 200, 'HTTPS da login sahifasi');
        T::ok(str_contains($out, 'setup_key'), 'kalit so‘raladi');
        [$c, $out] = Http::req('POST', "$base/setup.php", 'action=login&key=wrong');
        T::ok(str_contains($out, 'noto‘g‘ri'), 'noto‘g‘ri kalit rad');
        [$c, $out, $h] = Http::req('POST', "$base/setup.php", 'action=login&key=' . urlencode($cfg['setup_key']));
        $cookieLine = implode("\n", array_filter($h, fn($x) => stripos($x, 'Set-Cookie: TBSETUP=') === 0));
        T::ok(stripos($cookieLine, 'secure') !== false && stripos($cookieLine, 'httponly') !== false && stripos($cookieLine, 'samesite=strict') !== false, 'session cookie secure+httponly+samesite');
        preg_match('/TBSETUP=([^;]+)/', $cookieLine, $m);
        $cookie = 'Cookie: TBSETUP=' . ($m[1] ?? '');
        T::ok(str_contains($out, 'mock_tanishuv_bot'), 'getMe natijasi ko‘rsatildi');
        T::ok(str_contains($out, 'Webhook URL'), 'getWebhookInfo natijasi ko‘rsatildi');
        T::ok(!str_contains($out, 'TEST_TOKEN') && !str_contains($out, $cfg['webhook_secret']) && !str_contains($out, $cfg['db']['pass'] . '<'), 'sahifada token/secret yo‘q');
        preg_match('/name="csrf" value="([0-9a-f]+)"/', $out, $cm);
        $csrf = $cm[1] ?? '';
        T::ok(strlen($csrf) === 64, 'CSRF token');
        [$c] = Http::req('POST', "$base/setup.php", 'action=setwebhook&csrf=bad', [$cookie]);
        T::eq($c, 400, 'CSRF siz setWebhook rad');
        [$c, $out] = Http::req('POST', "$base/setup.php", 'action=setwebhook&csrf=' . $csrf, [$cookie]);
        T::ok(str_contains($out, 'setWebhook: OK'), 'setWebhook bajarildi');
        $calls = array_map(fn($l) => json_decode($l, true), array_filter(explode("\n", (string)file_get_contents($log))));
        $sw = array_values(array_filter($calls, fn($c) => $c['method'] === 'setWebhook'))[0]['body'] ?? [];
        T::eq($sw['url'] ?? null, 'https://example.test/tanishuv-bot/public/webhook.php', 'webhook URL');
        T::eq($sw['secret_token'] ?? null, $cfg['webhook_secret'], 'secret_token berildi');
        T::eq($sw['allowed_updates'] ?? null, ['message', 'callback_query', 'pre_checkout_query'], 'allowed_updates');
        T::eq($sw['drop_pending_updates'] ?? null, false, 'drop_pending_updates=false');
        T::ok(count(array_filter($calls, fn($c) => $c['method'] === 'setMyCommands')) === 4, 'buyruqlar 3 tilda o‘rnatildi');
        [$c, $out] = Http::req('POST', "$base/setup.php", 'action=close&csrf=' . $csrf, [$cookie]);
        T::ok(str_contains($out, 'yopildi'), 'setup yopildi');
        T::eq(App::db()->setting('setup_closed'), '1', 'bazada setup_closed=1');
        [$c] = Http::req('GET', "$base/setup.php");
        T::eq($c, 403, 'yopilgan setup 403');
        App::db()->setSetting('setup_closed', '0');
    } finally {
        foreach (glob(TB_ROOT . '/storage/sessions/sess_*') ?: [] as $sf) {
            @unlink($sf);
        }
        @rmdir(TB_ROOT . '/storage/sessions');
        Http::stop();
        @unlink($cfgFile);
        @unlink($log);
    }
});

$t('xavfsizlik: config tekshiruvi, maxfiy qiymatlar logda yo‘q, PDO sozlamalari', function () {
    $good = T::$cfg;
    App::setConfig($good);
    T::eq(App::configProblems(), [], 'test config muammosiz');
    $bad = $good;
    $bad['cron_key'] = $bad['webhook_secret'];
    App::setConfig($bad);
    T::ok(App::configProblems() !== [], 'bir xil kalitlar rad etiladi');
    $bad = $good;
    $bad['setup_key'] = 'short';
    App::setConfig($bad);
    T::ok(App::configProblems() !== [], 'qisqa kalit rad etiladi');
    App::setConfig($good);
    $s = \TB\Log::scrub('token=' . $good['bot_token'] . ' pass=' . $good['db']['pass'] . ' 987654321:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA');
    T::ok(!str_contains($s, $good['bot_token']) && !str_contains($s, 'tbpass') && !str_contains($s, 'AAAAAAAAAAAAAAAA'), 'Log::scrub token/parolni yashiradi');
    $pdo = App::db()->pdo;
    T::eq($pdo->getAttribute(\PDO::ATTR_ERRMODE), \PDO::ERRMODE_EXCEPTION, 'ERRMODE_EXCEPTION');
    T::eq((bool)$pdo->getAttribute(\PDO::ATTR_EMULATE_PREPARES), false, 'EMULATE_PREPARES=false');
    T::eq(App::db()->val('SELECT @@session.time_zone'), '+00:00', 'DB sessiyasi UTC');
    T::eq(App::db()->val('SELECT @@character_set_connection'), 'utf8mb4', 'utf8mb4');
    T::eq(date_default_timezone_get(), 'UTC', 'PHP UTC');
    $bad = 0;
    foreach (App::db()->all("SELECT table_name AS t, engine AS e, table_collation AS c FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name LIKE 'tb\\_%'") as $r) {
        if ($r['e'] !== 'InnoDB' || !str_starts_with((string)$r['c'], 'utf8mb4')) {
            $bad++;
        }
    }
    T::eq($bad, 0, 'barcha tb_ jadvallar InnoDB + utf8mb4');
    $sql = (string)file_get_contents(TB_ROOT . '/sql/database.sql') . (string)file_get_contents(TB_ROOT . '/sql/migration.sql');
    $code = preg_replace('/^--.*$/m', '', $sql);
    T::ok(!preg_match('/\b(DROP|TRUNCATE|ALTER)\b/i', (string)$code), 'SQL da DROP/TRUNCATE/ALTER yo‘q');
    preg_match_all('/CREATE TABLE IF NOT EXISTS `([a-z_]+)`/', (string)$code, $m);
    T::eq(count(array_filter($m[1], fn($x) => !str_starts_with($x, 'tb_'))), 0, 'barcha jadvallar tb_ prefiksli');
    $ex = (string)file_get_contents(TB_ROOT . '/config.example.php');
    T::ok(preg_match("/'(bot_token|pass|webhook_secret|setup_key|cron_key|hmac_secret)' => '[^']+'/", $ex) === 0, 'config.example.php da maxfiy qiymat yo‘q');
});

$t('document root: ichki papkalar .htaccess bilan yopilgan, ochiq qism faqat public/', function () {
    foreach (['src', 'locales', 'sql', 'docs', 'tests', 'storage'] as $d) {
        $h = (string)@file_get_contents(TB_ROOT . "/$d/.htaccess");
        T::ok(str_contains($h, 'Require all denied') && str_contains($h, 'Deny from all'), "$d/.htaccess yopilgan");
    }
    $root = (string)file_get_contents(TB_ROOT . '/.htaccess');
    T::ok(str_contains($root, 'src|locales|sql|config|docs|tests|storage'), 'ildiz .htaccess ichki papkalarni yopadi');
    T::ok(str_contains($root, 'Nginx'), 'Nginx ogohlantirishi yozilgan');
    $pub = array_map('basename', glob(TB_ROOT . '/public/*'));
    sort($pub);
    T::eq($pub, ['bank-webhook.php', 'cron.php', 'hmac-test.html', 'index.php', 'setup.php', 'sms-webhook.php', 'webhook.php'], 'public/ da faqat kerakli fayllar');
    // src fayllari to‘g‘ridan-to‘g‘ri ishga tushirilganda hech narsa chiqarmaydi
    foreach (glob(TB_ROOT . '/src/*.php') as $f) {
        if (basename($f) === 'bootstrap.php') {
            continue;
        }
        $out = shell_exec(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($f) . ' 2>&1');
        T::eq((string)$out, '', basename($f) . ' to‘g‘ridan-to‘g‘ri ochilganda bo‘sh');
    }
    foreach (['config.example.php', 'locales/uz.php'] as $f) {
        T::eq((string)shell_exec(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg(TB_ROOT . '/' . $f) . ' 2>&1'), '', "$f to‘g‘ridan-to‘g‘ri ochilganda bo‘sh");
    }
});
