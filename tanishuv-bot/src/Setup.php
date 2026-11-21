<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * O‘rnatish sahifasi: faqat HTTPS, setup_key bilan kirish, 15 daqiqalik secure/httponly/samesite
 * session, CSRF, getMe/getWebhookInfo, setWebhook va setupni bazada yopish.
 */
final class Setup
{
    public const SESSION_TTL = 900;

    public static function isHttps(array $s, bool $trustProxy = false): bool
    {
        if (!empty($s['HTTPS']) && strtolower((string)$s['HTTPS']) !== 'off') {
            return true;
        }
        if ((string)($s['SERVER_PORT'] ?? '') === '443') {
            return true;
        }
        if ($trustProxy && strtolower((string)($s['HTTP_X_FORWARDED_PROTO'] ?? '')) === 'https') {
            return true;
        }
        return false;
    }

    private static function h($s): string
    {
        return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }

    private static function page(string $body, int $code = 200): void
    {
        http_response_code($code);
        header('Content-Type: text/html; charset=utf-8');
        header('Cache-Control: no-store');
        header('X-Frame-Options: DENY');
        header('X-Content-Type-Options: nosniff');
        header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
        header('Referrer-Policy: no-referrer');
        echo '<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            . '<title>Tanishuv bot — setup</title><style>body{font-family:system-ui,sans-serif;max-width:720px;margin:0 auto;padding:16px;line-height:1.5;background:#f6f7f9;color:#111}'
            . '.c{background:#fff;border-radius:12px;padding:16px;margin:12px 0;box-shadow:0 1px 3px #0002}.ok{color:#0a7d32}.bad{color:#b00020}'
            . 'button,input{font-size:16px;padding:10px 14px;border-radius:8px;border:1px solid #bbb;width:100%;box-sizing:border-box;margin:6px 0}'
            . 'button{background:#2563eb;color:#fff;border:0}button.d{background:#b00020}table{width:100%;border-collapse:collapse}td{padding:4px;border-bottom:1px solid #eee;vertical-align:top;word-break:break-word}</style></head><body>'
            . '<h2>Tanishuv bot — o‘rnatish</h2>' . $body . '</body></html>';
        exit;
    }

    public static function run(): void
    {
        if (!self::isHttps($_SERVER)) {
            self::page('<div class="c bad">Setup faqat HTTPS orqali ishlaydi. Manzilni https:// bilan oching.</div>', 403);
        }
        try {
            App::loadConfig();
        } catch (\Throwable $e) {
            self::page('<div class="c bad">config.php topilmadi yoki xato. ORNATISH_UZ.txt dagi 5-qadamni bajaring.</div>', 503);
        }
        if (!self::isHttps($_SERVER, (bool)App::cfg('trust_proxy_https'))) {
            self::page('<div class="c bad">Faqat HTTPS.</div>', 403);
        }
        $problems = App::configProblems();
        if ($problems) {
            self::page('<div class="c bad"><b>config.php xavfsiz emas:</b><br>' . implode('<br>', array_map([self::class, 'h'], $problems)) . '</div>', 503);
        }
        try {
            $db = App::db();
            $closed = $db->setting('setup_closed', '0') === '1';
        } catch (\Throwable $e) {
            Log::error('setup db', $e);
            self::page('<div class="c bad">MySQL ga ulanib bo‘lmadi yoki jadvallar yo‘q. config.php dagi db sozlamalarini tekshiring va database.sql ni import qiling.</div>', 503);
        }
        if ($closed) {
            self::page('<div class="c">Setup yopilgan. Qayta ochish uchun phpMyAdmin da <code>tb_settings</code> jadvalida <code>setup_closed</code> qiymatini 0 qiling.</div>', 403);
        }

        $dir = TB_ROOT . '/storage/sessions';
        if (!is_dir($dir)) {
            @mkdir($dir, 0700, true);
        }
        if (is_dir($dir) && is_writable($dir)) {
            session_save_path($dir);
        }
        $path = (string)(parse_url((string)App::cfg('public_url'), PHP_URL_PATH) ?: '/');
        session_name('TBSETUP');
        session_set_cookie_params(['lifetime' => 0, 'path' => rtrim($path, '/') . '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Strict']);
        ini_set('session.use_strict_mode', '1');
        ini_set('session.gc_maxlifetime', (string)self::SESSION_TTL);
        session_start();
        $now = time();
        if (!empty($_SESSION['auth']) && ($now - (int)($_SESSION['t'] ?? 0)) > self::SESSION_TTL) {
            $_SESSION = [];
            session_regenerate_id(true);
        }
        $msg = '';
        $post = ($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST';
        if ($post && ($_POST['action'] ?? '') === 'login') {
            if (hash_equals((string)App::cfg('setup_key'), (string)($_POST['key'] ?? ''))) {
                session_regenerate_id(true);
                $_SESSION = ['auth' => 1, 't' => $now, 'csrf' => bin2hex(random_bytes(32))];
            } else {
                usleep(800000);
                $msg = '<div class="c bad">Kalit noto‘g‘ri.</div>';
            }
        }
        if (empty($_SESSION['auth'])) {
            self::page($msg . '<div class="c"><form method="post"><input type="hidden" name="action" value="login">'
                . '<label>setup_key (config.php dan)</label><input type="password" name="key" autocomplete="off" required>'
                . '<button type="submit">Kirish</button></form></div>');
        }
        $_SESSION['t'] = $now;
        $csrf = (string)$_SESSION['csrf'];

        if ($post && ($_POST['action'] ?? '') !== 'login') {
            if (!hash_equals($csrf, (string)($_POST['csrf'] ?? ''))) {
                self::page('<div class="c bad">CSRF tekshiruvi o‘tmadi. Sahifani yangilang.</div>', 400);
            }
            $act = (string)($_POST['action'] ?? '');
            if ($act === 'setwebhook') {
                $msg = self::setWebhook();
            } elseif ($act === 'close') {
                $db->setSetting('setup_closed', '1');
                $db->exec("INSERT INTO tb_admin_audit (admin_id, action, target, details, created_at) VALUES (0, 'setup.close', NULL, NULL, UTC_TIMESTAMP())");
                $_SESSION = [];
                session_destroy();
                self::page('<div class="c ok">Setup bazada yopildi. Endi bu sahifa ishlamaydi.</div>');
            } elseif ($act === 'logout') {
                $_SESSION = [];
                session_destroy();
                self::page('<div class="c">Chiqdingiz.</div>');
            }
        }
        self::page($msg . self::status($csrf));
    }

    private static function setWebhook(): string
    {
        $url = rtrim((string)App::cfg('public_url'), '/') . '/webhook.php';
        if (!str_starts_with($url, 'https://')) {
            return '<div class="c bad">public_url https:// bilan boshlanishi kerak.</div>';
        }
        $r = App::tg()->call('setWebhook', [
            'url' => $url,
            'secret_token' => (string)App::cfg('webhook_secret'),
            'allowed_updates' => ['message', 'callback_query', 'pre_checkout_query'],
            'drop_pending_updates' => false,
            'max_connections' => 10,
        ], 15);
        $out = !empty($r['ok'])
            ? '<div class="c ok">setWebhook: OK</div>'
            : '<div class="c bad">setWebhook xatosi: ' . self::h($r['description'] ?? '') . '</div>';
        foreach ([null, 'uz', 'ru', 'en'] as $l) {
            $lang = $l ?? 'uz';
            $cmds = [];
            foreach (Router::COMMANDS as $c) {
                $cmds[] = ['command' => $c, 'description' => Lang::t($lang, 'cmdhelp.' . $c)];
            }
            $p = ['commands' => $cmds];
            if ($l !== null) {
                $p['language_code'] = $l;
            }
            App::tg()->call('setMyCommands', $p, 10);
        }
        return $out;
    }

    private static function status(string $csrf): string
    {
        $rows = [];
        $rows[] = ['PHP', PHP_VERSION, PHP_VERSION_ID >= 80100];
        $rows[] = ['64-bit', PHP_INT_SIZE * 8 . '-bit', PHP_INT_SIZE >= 8];
        foreach (['curl', 'pdo_mysql', 'mbstring'] as $e) {
            $rows[] = [$e, extension_loaded($e) ? 'bor' : 'yo‘q', extension_loaded($e)];
        }
        $db = App::db();
        $tables = (int)$db->val("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name LIKE 'tb\\_%'");
        $rows[] = ['tb_ jadvallar', (string)$tables, $tables >= 25];
        $rows[] = ['Vaqt (DB, UTC)', (string)$db->val('SELECT UTC_TIMESTAMP()'), true];
        $rows[] = ['storage/ yozish', is_writable(TB_ROOT . '/storage') ? 'mumkin' : 'mumkin emas', is_writable(TB_ROOT . '/storage')];
        $rows[] = ['admin_ids', implode(', ', array_map('intval', (array)App::cfg('admin_ids'))), (bool)App::cfg('admin_ids')];
        $me = App::tg()->call('getMe', [], 10);
        $rows[] = ['getMe', !empty($me['ok']) ? '@' . ($me['result']['username'] ?? '?') . ' (id ' . ($me['result']['id'] ?? '?') . ')' : 'xato: ' . ($me['description'] ?? ''), !empty($me['ok'])];
        $wi = App::tg()->call('getWebhookInfo', [], 10);
        $expected = rtrim((string)App::cfg('public_url'), '/') . '/webhook.php';
        if (!empty($wi['ok'])) {
            $w = $wi['result'];
            $rows[] = ['Webhook URL', (string)($w['url'] ?? '') ?: '(o‘rnatilmagan)', ($w['url'] ?? '') === $expected];
            $rows[] = ['Kutilayotgan update', (string)($w['pending_update_count'] ?? 0), true];
            $rows[] = ['allowed_updates', implode(', ', (array)($w['allowed_updates'] ?? [])), true];
            if (!empty($w['last_error_message'])) {
                $rows[] = ['Oxirgi xato', (string)$w['last_error_message'] . ' (' . gmdate('Y-m-d H:i', (int)($w['last_error_date'] ?? 0)) . ' UTC)', false];
            }
        } else {
            $rows[] = ['getWebhookInfo', 'xato: ' . ($wi['description'] ?? ''), false];
        }
        $html = '<div class="c"><table>';
        foreach ($rows as [$k, $v, $ok]) {
            $html .= '<tr><td>' . self::h($k) . '</td><td class="' . ($ok ? 'ok' : 'bad') . '">' . ($ok ? '✔ ' : '✘ ') . self::h($v) . '</td></tr>';
        }
        $html .= '</table></div>';
        $f = static fn(string $action, string $label, string $cls = '') =>
            '<form method="post"><input type="hidden" name="csrf" value="' . self::h($csrf) . '"><input type="hidden" name="action" value="' . $action . '"><button class="' . $cls . '" type="submit">' . $label . '</button></form>';
        $html .= '<div class="c"><p>Webhook manzili: <b>' . self::h($expected) . '</b></p>' . $f('setwebhook', 'setWebhook (secret_token bilan)') . '</div>';
        $html .= '<div class="c"><p>Hammasi ishlagach setupni yoping:</p>' . $f('close', 'Setupni bazada yopish', 'd') . $f('logout', 'Chiqish') . '</div>';
        return $html;
    }
}
