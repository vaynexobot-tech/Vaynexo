<?php
declare(strict_types=1);

/*
 * Avtomatik testlar: haqiqiy bir martalik MySQL/MariaDB bazasi + mock Telegram transport.
 * Ishga tushirish:  php tests/run.php
 * DB: TB_TEST_DB_HOST, TB_TEST_DB_PORT, TB_TEST_DB_USER, TB_TEST_DB_PASS (standart 127.0.0.1 / tb / tbpass)
 * Haqiqiy Telegram API chaqirilmaydi, haqiqiy Stars xaridi qilinmaydi.
 */

namespace TB\Tests;

use TB\App;
use TB\Lang;
use TB\Menu;
use TB\Users;

require __DIR__ . '/lib.php';

$tests = [];
$only = $argv[1] ?? null;
$t = static function (string $name, callable $fn) use (&$tests): void {
    $tests[$name] = $fn;
};

foreach (glob(__DIR__ . '/cases/*.php') as $f) {
    require $f;
}

T::setup();
$start = microtime(true);
echo "Test bazasi: " . T::$dbName . "\n";
foreach ($tests as $name => $fn) {
    if ($only !== null && !str_contains($name, $only)) {
        continue;
    }
    T::$current = $name;
    T::$tg->reset();
    App::$hooks = [];
    T::setAdmins([9000001, 9000002]);
    Menu::reset();
    \TB\Settings::set('likes_gate', '0');   // standart '1'; Premium-qulf alohida testda tekshiriladi
    $before = count(T::$fail);
    try {
        $fn();
    } catch (\Throwable $e) {
        T::$fail[] = "$name: istisno " . get_class($e) . ': ' . $e->getMessage() . ' @' . basename($e->getFile()) . ':' . $e->getLine();
        echo "    ✘ istisno: " . $e->getMessage() . ' @' . basename($e->getFile()) . ':' . $e->getLine() . "\n";
        if (App::$db && App::$db->inTx()) {
            App::$db->rollBack();
        }
    }
    echo (count(T::$fail) === $before ? "✔ " : "✘ ") . $name . "\n";
}
$keep = in_array('--keep', $argv, true);
T::teardown($keep);
printf("\nNatija: %d ta tekshiruv o‘tdi, %d ta xato. Vaqt: %.1f s\n", T::$pass, count(T::$fail), microtime(true) - $start);
foreach (T::$fail as $f) {
    echo " - $f\n";
}
exit(T::$fail ? 1 : 0);
