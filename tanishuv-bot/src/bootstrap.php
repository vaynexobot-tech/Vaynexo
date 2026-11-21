<?php
declare(strict_types=1);

/*
 * Tanishuv bot: umumiy yuklovchi.
 * Bu fayl to‘g‘ridan-to‘g‘ri ochilganda hech narsa chiqarmaydi.
 */

if (!defined('TB_ROOT')) {
    define('TB_ROOT', dirname(__DIR__));
}

(static function (): void {
    $problems = [];
    if (PHP_VERSION_ID < 80100) {
        $problems[] = 'PHP 8.1 yoki undan yangi versiya kerak (hozir: ' . PHP_VERSION . ')';
    }
    if (PHP_INT_SIZE < 8) {
        $problems[] = '64-bit PHP kerak (Telegram ID lari katta sonlar)';
    }
    foreach (['curl', 'pdo_mysql', 'mbstring', 'json'] as $ext) {
        if (!extension_loaded($ext)) {
            $problems[] = 'PHP kengaytmasi yo‘q: ' . $ext;
        }
    }
    if ($problems) {
        if (PHP_SAPI !== 'cli') {
            http_response_code(500);
            header('Content-Type: text/plain; charset=utf-8');
        }
        echo "Server talablari bajarilmagan:\n- " . implode("\n- ", $problems) . "\n";
        exit(1);
    }
})();

date_default_timezone_set('UTC');
mb_internal_encoding('UTF-8');
ini_set('display_errors', '0');
error_reporting(E_ALL);

spl_autoload_register(static function (string $class): void {
    if (strncmp($class, 'TB\\', 3) !== 0) {
        return;
    }
    $file = TB_ROOT . '/src/' . str_replace('\\', '/', substr($class, 3)) . '.php';
    if (is_file($file)) {
        require $file;
    }
});
