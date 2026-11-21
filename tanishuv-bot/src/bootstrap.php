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
    if (PHP_VERSION_ID < 70400) {
        $problems[] = 'PHP 7.4 yoki undan yangi versiya kerak (hozir: ' . PHP_VERSION . ')';
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

// PHP 7.4 uchun: PHP 8 funksiyalari (PHP 8+ da bu bloklar o‘tkazib yuboriladi)
if (!function_exists('str_contains')) {
    function str_contains(string $haystack, string $needle): bool
    {
        return $needle === '' || strpos($haystack, $needle) !== false;
    }
}
if (!function_exists('str_starts_with')) {
    function str_starts_with(string $haystack, string $needle): bool
    {
        return $needle === '' || strncmp($haystack, $needle, strlen($needle)) === 0;
    }
}
if (!function_exists('str_ends_with')) {
    function str_ends_with(string $haystack, string $needle): bool
    {
        return $needle === '' || substr($haystack, -strlen($needle)) === $needle;
    }
}
if (!function_exists('array_is_list')) {
    function array_is_list(array $array): bool
    {
        $i = 0;
        foreach ($array as $k => $_) {
            if ($k !== $i++) {
                return false;
            }
        }
        return true;
    }
}

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
