<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

final class ConfigError extends \RuntimeException {}

/**
 * Global holat: konfiguratsiya, DB ulanishi va Telegram transporti.
 */
final class App
{
    public static array $cfg = [];
    public static ?Db $db = null;
    public static ?Transport $tg = null;
    /** Testlar uchun: nuqta nomi => closure. Ishlab chiqarishda bo‘sh. */
    public static array $hooks = [];

    public static function defaults(): array
    {
        return [
            'bot_token' => '',
            'bot_username' => '',
            'db' => ['host' => 'localhost', 'port' => 3306, 'name' => '', 'user' => '', 'pass' => ''],
            'public_url' => '',
            'admin_ids' => [],
            'webhook_secret' => '',
            'setup_key' => '',
            'cron_key' => '',
            'support_contact' => '',
            'telegram_api_base' => 'https://api.telegram.org',
            'limits' => [
                'free_likes' => 30, 'free_supers' => 1,
                'premium_likes' => 300, 'premium_supers' => 10,
            ],
            'bank' => ['enabled' => false, 'hmac_secret' => '', 'max_skew' => 300],
            'cron_time_budget' => 20,
            'webhook_send_budget' => 4,
            'trust_proxy_https' => false,
        ];
    }

    public static function loadConfig(): array
    {
        $file = TB_ROOT . '/config.php';
        if (in_array(PHP_SAPI, ['cli', 'cli-server'], true) && getenv('TB_CONFIG')) {
            $file = (string)getenv('TB_CONFIG');
        }
        if (!is_file($file)) {
            throw new ConfigError('config.php topilmadi');
        }
        $cfg = require $file;
        if (!is_array($cfg)) {
            throw new ConfigError('config.php massiv qaytarmadi');
        }
        self::setConfig($cfg);
        return self::$cfg;
    }

    public static function setConfig(array $cfg): void
    {
        $d = self::defaults();
        foreach ($d as $k => $v) {
            if (is_array($v) && isset($cfg[$k]) && is_array($cfg[$k]) && $k !== 'admin_ids') {
                $cfg[$k] = $cfg[$k] + $v;
            }
        }
        self::$cfg = $cfg + $d;
    }

    public static function cfg(string $key, $default = null)
    {
        $cur = self::$cfg;
        foreach (explode('.', $key) as $p) {
            if (!is_array($cur) || !array_key_exists($p, $cur)) {
                return $default;
            }
            $cur = $cur[$p];
        }
        return $cur;
    }

    /** Konfiguratsiyadagi xavfsizlik muammolari (maxfiy qiymatlarni ko‘rsatmaydi). */
    public static function configProblems(): array
    {
        $p = [];
        $keys = ['webhook_secret', 'setup_key', 'cron_key'];
        $vals = [];
        foreach ($keys as $k) {
            $v = (string)self::cfg($k, '');
            if (strlen($v) < 32) {
                $p[] = "$k kamida 32 belgi bo‘lishi kerak";
            }
            if ($k === 'webhook_secret' && $v !== '' && !preg_match('/^[A-Za-z0-9_-]{1,256}$/', $v)) {
                $p[] = 'webhook_secret faqat A-Z, a-z, 0-9, _ va - belgilaridan iborat bo‘lsin';
            }
            $vals[$k] = $v;
        }
        if (count(array_unique(array_filter($vals))) !== count(array_filter($vals))) {
            $p[] = 'webhook_secret, setup_key va cron_key bir-biridan farqli bo‘lishi kerak';
        }
        if ((bool)self::cfg('bank.enabled')) {
            $b = (string)self::cfg('bank.hmac_secret', '');
            if (strlen($b) < 32) {
                $p[] = 'bank.hmac_secret kamida 32 belgi bo‘lishi kerak';
            } elseif (in_array($b, $vals, true)) {
                $p[] = 'bank.hmac_secret boshqa kalitlardan farqli bo‘lishi kerak';
            }
        }
        $sk = (string)self::cfg('bank.sms_key', '');
        if ($sk !== '') {
            if (strlen($sk) < 32 || !preg_match('/^[A-Za-z0-9_-]+$/', $sk)) {
                $p[] = 'bank.sms_key kamida 32 belgi (A-Z, a-z, 0-9, _ -) bo‘lishi kerak';
            } elseif (in_array($sk, $vals, true) || $sk === (string)self::cfg('bank.hmac_secret', '')) {
                $p[] = 'bank.sms_key boshqa kalitlardan farqli bo‘lishi kerak';
            }
        }
        return $p;
    }

    public static function db(): Db
    {
        if (self::$db === null) {
            self::$db = new Db((array)self::cfg('db'));
        }
        return self::$db;
    }

    public static function tg(): Transport
    {
        if (self::$tg === null) {
            self::$tg = new CurlTransport((string)self::cfg('bot_token'), (string)self::cfg('telegram_api_base'));
        }
        return self::$tg;
    }

    /** Ruxsat har safar configdan qayta o‘qiladi. */
    public static function isAdmin(int $id): bool
    {
        foreach ((array)self::cfg('admin_ids', []) as $a) {
            if ((int)$a === $id && $id > 0) {
                return true;
            }
        }
        return false;
    }

    public static function hook(string $point): void
    {
        if (isset(self::$hooks[$point])) {
            (self::$hooks[$point])();
        }
    }

    public static function secrets(): array
    {
        return array_values(array_filter([
            (string)self::cfg('bot_token', ''),
            (string)self::cfg('db.pass', ''),
            (string)self::cfg('webhook_secret', ''),
            (string)self::cfg('setup_key', ''),
            (string)self::cfg('cron_key', ''),
            (string)self::cfg('bank.hmac_secret', ''),
            (string)self::cfg('bank.sms_key', ''),
        ], static fn($s) => strlen($s) >= 4));
    }
}
