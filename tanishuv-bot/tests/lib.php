<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Bot;
use TB\Menu;
use TB\Outbox;

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}
define('TB_TESTS', __DIR__);
require dirname(__DIR__) . '/src/bootstrap.php';
require __DIR__ . '/MockTransport.php';

final class T
{
    public static MockTransport $tg;
    public static int $upd = 5000;
    public static array $cfg = [];
    public static string $dbName = '';
    public static string $cfgFile = '';
    public static int $pass = 0;
    public static array $fail = [];
    public static string $current = '';
    /** Barcha yuborilgan callback_data lar (64 bayt tekshiruvi uchun) */
    public static array $allCallbacks = [];

    public static function dbParams(): array
    {
        return [
            'host' => getenv('TB_TEST_DB_HOST') ?: '127.0.0.1',
            'port' => (int)(getenv('TB_TEST_DB_PORT') ?: 3306),
            'user' => getenv('TB_TEST_DB_USER') ?: 'tb',
            'pass' => getenv('TB_TEST_DB_PASS') ?: 'tbpass',
        ];
    }

    /** Bir martalik test bazasi: tb_test_<tasodifiy>. Faqat shu baza yaratiladi va oxirida o‘chiriladi. */
    public static function setup(): void
    {
        $p = self::dbParams();
        self::$dbName = 'tb_test_' . bin2hex(random_bytes(4));
        $pdo = new \PDO("mysql:host={$p['host']};port={$p['port']};charset=utf8mb4", $p['user'], $p['pass'], [\PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION]);
        $pdo->exec('CREATE DATABASE `' . self::$dbName . '` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');
        $pdo->exec('USE `' . self::$dbName . '`');
        self::importSql($pdo, TB_ROOT . '/sql/database.sql');
        $secret = static fn() => bin2hex(random_bytes(32));
        self::$cfg = [
            'bot_token' => '123456:TEST_TOKEN_NOT_REAL_xxxxxxxxxxxxxxxxxxxxxxxx',
            'db' => ['host' => $p['host'], 'port' => $p['port'], 'name' => self::$dbName, 'user' => $p['user'], 'pass' => $p['pass']],
            'public_url' => 'https://example.test/tanishuv-bot/public',
            'admin_ids' => [9000001, 9000002],
            'webhook_secret' => $secret(),
            'setup_key' => $secret(),
            'cron_key' => $secret(),
            'support_contact' => '@support_test',
            'bank' => ['enabled' => true, 'hmac_secret' => $secret(), 'max_skew' => 300],
        ];
        self::writeConfig(self::$cfg);
        App::setConfig(self::$cfg);
        App::$db = null;
        self::$tg = new MockTransport();
        App::$tg = self::$tg;
    }

    public static function writeConfig(array $cfg, ?string $file = null): string
    {
        $file ??= sys_get_temp_dir() . '/tb_test_config_' . self::$dbName . '.php';
        file_put_contents($file, "<?php\nreturn " . var_export($cfg, true) . ";\n");
        self::$cfgFile = $file;
        return $file;
    }

    public static function importSql(\PDO $pdo, string $file): void
    {
        $sql = (string)file_get_contents($file);
        $sql = (string)preg_replace('/^--.*$/m', '', $sql);
        foreach (array_filter(array_map('trim', explode(";\n", $sql))) as $stmt) {
            $pdo->exec($stmt);
        }
    }

    public static function teardown(bool $keep = false): void
    {
        App::$db = null;
        if (!$keep && str_starts_with(self::$dbName, 'tb_test_')) {
            $p = self::dbParams();
            $pdo = new \PDO("mysql:host={$p['host']};port={$p['port']}", $p['user'], $p['pass']);
            $pdo->exec('DROP DATABASE IF EXISTS `' . self::$dbName . '`'); // faqat bir martalik test bazasi
        }
        if (self::$cfgFile && is_file(self::$cfgFile)) {
            @unlink(self::$cfgFile);
        }
    }

    /** Oldingi testlar profillari qidiruvga aralashmasligi uchun ularni yashiradi. */
    public static function isolate(): void
    {
        App::db()->exec("UPDATE tb_users SET status = 'suspended' WHERE status = 'active'");
    }

    public static function setAdmins(array $ids): void
    {
        self::$cfg['admin_ids'] = $ids;
        App::setConfig(self::$cfg);
    }

    // ---------------- update quruvchilar ----------------

    public static function from(int $uid, string $lc = 'uz'): array
    {
        return ['id' => $uid, 'is_bot' => false, 'first_name' => 'U' . $uid, 'username' => 'user' . $uid, 'language_code' => $lc];
    }

    public static function msgUpdate(int $uid, array $fields): array
    {
        return ['update_id' => ++self::$upd, 'message' => [
            'message_id' => self::$upd, 'from' => self::from($uid), 'chat' => ['id' => $uid, 'type' => 'private', 'username' => 'user' . $uid], 'date' => time(),
        ] + $fields];
    }

    public static function cbUpdate(int $uid, string $data, bool $textMsg = true): array
    {
        self::$allCallbacks[] = $data;
        $m = ['message_id' => 77, 'chat' => ['id' => $uid, 'type' => 'private'], 'date' => time()];
        if ($textMsg) {
            $m['text'] = 'x';
        } else {
            $m['photo'] = [['file_id' => 'p', 'width' => 1, 'height' => 1]];
        }
        return ['update_id' => ++self::$upd, 'callback_query' => ['id' => 'cq' . self::$upd, 'from' => self::from($uid), 'message' => $m, 'chat_instance' => '1', 'data' => $data]];
    }

    public static function send(array $update): array
    {
        $r = Bot::handleUpdate($update);
        Outbox::process(microtime(true) + 10, 5000);
        foreach (self::$tg->calls as $c) {
            foreach ((array)($c['params']['reply_markup']['inline_keyboard'] ?? []) as $row) {
                foreach ($row as $b) {
                    self::$allCallbacks[] = (string)($b['callback_data'] ?? '');
                }
            }
        }
        return $r;
    }

    public static function text(int $uid, string $text): array
    {
        return self::send(self::msgUpdate($uid, ['text' => $text]));
    }

    public static function photo(int $uid, string $fid, array $extra = []): array
    {
        return self::send(self::msgUpdate($uid, ['photo' => [['file_id' => $fid . '_s', 'width' => 90, 'height' => 90], ['file_id' => $fid, 'width' => 800, 'height' => 800]]] + $extra));
    }

    public static function cb(int $uid, string $data, bool $textMsg = true): array
    {
        return self::send(self::cbUpdate($uid, $data, $textMsg));
    }

    // ---------------- yordamchilar ----------------

    public static function user(int $uid): ?array
    {
        return App::db()->one('SELECT * FROM tb_users WHERE id = ?', [$uid]);
    }

    public static function lastText(int $uid): string
    {
        foreach (array_reverse(self::$tg->to($uid)) as $c) {
            if (isset($c['params']['text']) || isset($c['params']['caption'])) {
                return (string)($c['params']['text'] ?? $c['params']['caption']);
            }
        }
        return '';
    }

    public static function texts(int $uid): array
    {
        $out = [];
        foreach (self::$tg->to($uid) as $c) {
            if (isset($c['params']['text']) || isset($c['params']['caption'])) {
                $out[] = (string)($c['params']['text'] ?? $c['params']['caption']);
            }
        }
        return $out;
    }

    /** Oxirgi inline klaviaturadan prefiks bo‘yicha callback_data topadi. */
    public static function data(int $uid, string $prefix): ?string
    {
        foreach (array_reverse(self::$tg->to($uid)) as $c) {
            foreach ((array)($c['params']['reply_markup']['inline_keyboard'] ?? []) as $row) {
                foreach ($row as $b) {
                    if (str_starts_with((string)($b['callback_data'] ?? ''), $prefix)) {
                        return $b['callback_data'];
                    }
                }
            }
        }
        return null;
    }

    public static function lastReplyKeyboard(int $uid): ?array
    {
        foreach (array_reverse(self::$tg->to($uid)) as $c) {
            if (isset($c['params']['reply_markup']['keyboard'])) {
                return $c['params']['reply_markup']['keyboard'];
            }
        }
        return null;
    }

    public static function register(int $uid, string $lang = 'uz', string $name = 'Test', string $gender = 'm', int $region = 1, array $ints = ['music'], bool $tgPhoto = false, int $age = 25, string $goal = 'serious'): void
    {
        if ($tgPhoto) {
            self::$tg->profilePhotos[$uid] = 'TGPHOTO_' . $uid;
        }
        self::text($uid, '/start');
        self::cb($uid, 'lang:' . $lang);
        self::cb($uid, 'reg:age:yes');
        self::text($uid, (string)$age);
        self::text($uid, $name);
        if ($tgPhoto) {
            self::cb($uid, 'reg:ph:tg', false);
        } else {
            self::photo($uid, 'PH_' . $uid);
            self::cb($uid, 'reg:ph:done');
        }
        self::cb($uid, 'reg:g:' . $gender);
        self::cb($uid, 'reg:gl:' . $goal);
        self::cb($uid, 'reg:r:' . $region);
        foreach ($ints as $i) {
            self::cb($uid, 'reg:i:' . $i);
        }
        self::cb($uid, 'reg:i:done');
        self::cb($uid, 'reg:ok', false);
        Menu::reset();
    }

    // ---------------- assertions ----------------

    public static function ok(bool $cond, string $what): void
    {
        if ($cond) {
            self::$pass++;
        } else {
            self::$fail[] = self::$current . ': ' . $what;
            echo "    ✘ $what\n";
        }
    }

    public static function eq(mixed $a, mixed $b, string $what): void
    {
        $ok = $a === $b;
        if (!$ok) {
            $what .= ' (kutilgan ' . var_export($b, true) . ', olindi ' . var_export($a, true) . ')';
        }
        self::ok($ok, $what);
    }
}
