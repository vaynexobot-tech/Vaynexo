<?php
declare(strict_types=1);

/*
 * Parallel test ishchisi: alohida PHP jarayoni. TB_CONFIG dagi test bazasiga ulanadi,
 * mock transport bilan bitta update ni qayta ishlaydi va natijani JSON qilib chiqaradi.
 * Ishlatish: php tests/worker.php <update.json> <start_at_unix_float>
 */

if (PHP_SAPI !== 'cli') {
    exit;
}

require dirname(__DIR__) . '/src/bootstrap.php';
require __DIR__ . '/MockTransport.php';

TB\App::loadConfig();
TB\App::$tg = new TB\Tests\MockTransport();
$upd = json_decode((string)file_get_contents($argv[1]), true);
$startAt = (float)($argv[2] ?? 0);
TB\App::db(); // ulanishni oldindan ochamiz
while (microtime(true) < $startAt) {
    usleep(500);
}
try {
    $r = TB\Bot::handleUpdate($upd);
    echo json_encode(['status' => $r['status']]);
} catch (Throwable $e) {
    echo json_encode(['status' => 'error', 'error' => get_class($e) . ': ' . $e->getMessage()]);
}
