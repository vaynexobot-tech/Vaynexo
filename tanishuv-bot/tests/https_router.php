<?php
// Test routeri: HTTPS ni simulyatsiya qiladi va public/ fayllarini ochadi (faqat php -S uchun).
if (PHP_SAPI !== 'cli-server') {
    exit;
}
$_SERVER['HTTPS'] = 'on';
$path = (string)parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$file = realpath(dirname(__DIR__) . '/public/' . basename($path));
if ($file === false || !str_starts_with($file, realpath(dirname(__DIR__) . '/public') . '/') || !str_ends_with($file, '.php')) {
    http_response_code(404);
    exit;
}
require $file;
