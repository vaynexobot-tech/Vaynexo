<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Bot;
use TB\Lang;
use TB\Limits;
use TB\Search;
use TB\Users;

function order(int $uid, string $code, ?string $aud = null): array
{
    $db = App::db();
    if ($aud === null) {
        $pid = (int)$db->val('SELECT id FROM tb_products WHERE code = ?', [$code]);
        T::cb($uid, 'pm:b:' . $pid);
    } else {
        T::cb($uid, 'bs:' . $aud);
    }
    $inv = T::$tg->last($uid, 'sendInvoice');
    return $db->one('SELECT * FROM tb_orders WHERE id = ?', [(string)($inv['params']['payload'] ?? '')]);
}

function pcq(int $uid, string $payload, int $amount, string $cur = 'XTR'): ?bool
{
    T::$tg->reset();
    Bot::handleUpdate(['update_id' => ++T::$upd, 'pre_checkout_query' => [
        'id' => 'pcq' . T::$upd, 'from' => T::from($uid), 'currency' => $cur, 'total_amount' => $amount, 'invoice_payload' => $payload,
    ]]);
    $a = T::$tg->byMethod('answerPreCheckoutQuery');
    return $a ? (bool)$a[0]['params']['ok'] : null;
}

function payUpdate(int $uid, string $payload, int $amount, string $charge, string $cur = 'XTR'): array
{
    return T::msgUpdate($uid, ['successful_payment' => [
        'currency' => $cur, 'total_amount' => $amount, 'invoice_payload' => $payload,
        'telegram_payment_charge_id' => $charge, 'provider_payment_charge_id' => '',
    ]]);
}

$t('stars: sendInvoice XTR, provider_token bo‘sh, buyurtma snapshot', function () {
    $u = 6001;
    T::register($u, 'uz', 'Payer', 'm', 1);
    T::$tg->reset();
    $o = order($u, 'premium_7');
    $inv = T::$tg->last($u, 'sendInvoice');
    T::ok($inv !== null, 'sendInvoice yuborildi');
    T::eq($inv['params']['currency'], 'XTR', 'currency=XTR');
    T::eq($inv['params']['provider_token'], '', 'provider_token bo‘sh');
    T::eq($inv['params']['payload'], $o['id'], 'payload = order ID');
    T::eq($inv['params']['prices'][0]['amount'], 120, 'narx 120');
    T::eq([(int)$o['user_id'], $o['kind'], (int)$o['days'], (int)$o['amount'], $o['currency'], $o['status'], $o['audience']], [$u, 'premium', 7, 120, 'XTR', 'pending', null], 'snapshot maydonlari');
    T::ok(preg_match('/^[0-9a-f]{32}$/', $o['id']) === 1, 'order ID tasodifiy 32 hex');
    $b = order($u, 'boost', 'f');
    T::eq([$b['kind'], $b['audience'], (int)$b['amount'], (int)$b['days']], ['boost', 'f', 30, 1], 'boost snapshot (audience)');
});

$t('stars: pre_checkout egasi, summa, valyuta, order, muddat va profil holatini tekshiradi', function () {
    $u = 6101;
    $other = 6102;
    T::register($u, 'ru', 'Ivan', 'm', 1);
    T::register($other, 'uz', 'Boshqa', 'm', 1);
    $o = order($u, 'premium_1');
    T::eq(pcq($other, $o['id'], 25), false, 'begona egasi rad');
    T::eq(pcq($u, $o['id'], 24), false, 'noto‘g‘ri summa rad');
    T::eq(pcq($u, $o['id'], 25, 'USD'), false, 'noto‘g‘ri valyuta rad');
    T::eq(pcq($u, str_repeat('a', 32), 25), false, 'mavjud bo‘lmagan order rad');
    T::eq(pcq($u, 'garbage', 25), false, 'noto‘g‘ri payload rad');
    T::eq(pcq($u, $o['id'], 25), true, 'to‘g‘ri so‘rov qabul');
    T::eq(T::$tg->byMethod('answerPreCheckoutQuery')[0]['params']['pre_checkout_query_id'] ?? null, 'pcq' . T::$upd, 'javob shu query ga');
    $db = App::db();
    $db->exec('UPDATE tb_orders SET expires_at = UTC_TIMESTAMP() - INTERVAL 1 SECOND WHERE id = ?', [$o['id']]);
    T::eq(pcq($u, $o['id'], 25), false, 'muddati o‘tgan order rad');
    $db->exec('UPDATE tb_orders SET expires_at = UTC_TIMESTAMP() + INTERVAL 1 HOUR, created_at = UTC_TIMESTAMP() - INTERVAL 25 HOUR WHERE id = ?', [$o['id']]);
    T::eq(pcq($u, $o['id'], 25), false, '24 soatdan eski order rad');
    $db->exec('UPDATE tb_orders SET created_at = UTC_TIMESTAMP() WHERE id = ?', [$o['id']]);
    $db->exec("UPDATE tb_users SET status = 'suspended' WHERE id = ?", [$u]);
    T::eq(pcq($u, $o['id'], 25), false, 'suspended profil rad');
    $db->exec("UPDATE tb_users SET status = 'active' WHERE id = ?", [$u]);
    $db->exec("UPDATE tb_orders SET status = 'paid' WHERE id = ?", [$o['id']]);
    T::eq(pcq($u, $o['id'], 25), false, 'pending bo‘lmagan order rad');
    $db->exec("UPDATE tb_orders SET status = 'pending' WHERE id = ?", [$o['id']]);
    $err = T::$tg->byMethod('answerPreCheckoutQuery')[0]['params']['error_message'] ?? '';
    T::eq($err, Lang::t('ru', 'pay.err_order'), 'xato xabari foydalanuvchi tilida');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_outbox WHERE method = 'answerPreCheckoutQuery'"), 0, 'pre_checkout outbox orqali emas, to‘g‘ridan-to‘g‘ri');
});

$t('stars: pre_checkout outbox yoki broadcast lockini kutmaydi', function () {
    $u = 6151;
    T::register($u, 'uz', 'Tez', 'f', 1);
    $o = order($u, 'premium_1');
    $p = T::dbParams();
    $other = new \PDO("mysql:host={$p['host']};port={$p['port']};dbname=" . T::$dbName, $p['user'], $p['pass'], [\PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION]);
    $other->exec("SET SESSION innodb_lock_wait_timeout = 30");
    $other->query("SELECT GET_LOCK('" . App::db()->lockName('cron') . "', 0)")->fetchColumn();
    \TB\Outbox::add($u, 'sendMessage', ['chat_id' => $u, 'text' => 'x'], 'lock-test');
    $other->beginTransaction();
    $other->query('SELECT * FROM tb_outbox FOR UPDATE')->fetchAll();
    $other->query('SELECT * FROM tb_broadcasts FOR UPDATE')->fetchAll();
    $t0 = microtime(true);
    $ok = pcq($u, $o['id'], 25);
    $dt = microtime(true) - $t0;
    $other->rollBack();
    $other->query("SELECT RELEASE_LOCK('" . App::db()->lockName('cron') . "')");
    T::eq($ok, true, 'qulf ushlanganda ham javob berildi');
    T::ok($dt < 2.0, sprintf('javob tez: %.3f s (< 10 s talab)', $dt));
});

$t('stars: successful_payment idempotent, charge reuse rad, renewal qo‘shiladi', function () {
    $u = 6201;
    T::register($u, 'en', 'Buyer', 'm', 1);
    $db = App::db();
    $o1 = order($u, 'premium_1');
    $upd = payUpdate($u, $o1['id'], 25, 'CHARGE-1');
    T::send($upd);
    $o = $db->one('SELECT * FROM tb_orders WHERE id = ?', [$o1['id']]);
    T::eq([$o['status'], $o['telegram_payment_charge_id']], ['paid', 'CHARGE-1'], 'order paid va charge saqlandi');
    $until1 = (string)T::user($u)['premium_until'];
    T::ok(abs(strtotime($until1 . ' UTC') - (time() + 86400)) < 120, 'Premium 1 kun');
    T::ok(Users::isPremium(T::user($u)), 'Premium faol');

    // Ayni webhook qayta keldi
    $r = T::send($upd);
    T::eq($r['status'], 'duplicate', 'ayni update no-op');
    // Boshqa update_id, ayni order va charge
    T::send(payUpdate($u, $o1['id'], 25, 'CHARGE-1'));
    T::eq((string)T::user($u)['premium_until'], $until1, 'ayni charge qayta kelganda xizmat ikkinchi marta yoqilmadi');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_rejected_payments WHERE user_id = ?', [$u]), 0, 'idempotent takror rad sifatida yozilmadi');

    // Charge reuse: boshqa orderga eski charge
    $o2 = order($u, 'premium_3');
    T::$tg->reset();
    T::send(payUpdate($u, $o2['id'], 60, 'CHARGE-1'));
    T::eq($db->val('SELECT status FROM tb_orders WHERE id = ?', [$o2['id']]), 'pending', 'reuse charge order2 ni paid qilmadi');
    T::eq((string)T::user($u)['premium_until'], $until1, 'reuse charge xizmat bermadi');
    T::eq($db->val('SELECT reason FROM tb_rejected_payments WHERE user_id = ? ORDER BY id DESC LIMIT 1', [$u]), 'charge_reused', 'rejected jadvaliga yozildi');
    T::ok(count(T::$tg->to(9000001)) > 0 && count(T::$tg->to(9000002)) > 0, 'adminlar xabardor qilindi');

    // Noto‘g‘ri summa / valyuta / boshqa foydalanuvchi
    T::send(payUpdate($u, $o2['id'], 59, 'CHARGE-2'));
    T::send(payUpdate($u, $o2['id'], 60, 'CHARGE-3', 'USD'));
    $stranger = 6202;
    T::register($stranger, 'uz', 'Begona', 'f', 1);
    T::send(payUpdate($stranger, $o2['id'], 60, 'CHARGE-4'));
    T::send(payUpdate($u, str_repeat('b', 32), 60, 'CHARGE-5'));
    $reasons = array_column($db->all('SELECT reason FROM tb_rejected_payments ORDER BY id'), 'reason');
    foreach (['wrong_amount', 'wrong_currency', 'wrong_user', 'order_not_found'] as $rr) {
        T::ok(in_array($rr, $reasons, true), "rad sababi: $rr");
    }
    T::eq($db->val('SELECT status FROM tb_orders WHERE id = ?', [$o2['id']]), 'pending', 'noto‘g‘ri to‘lovlar orderni yopmadi');
    T::eq(T::user($stranger)['premium_until'], null, 'begona premium olmadi');

    // To‘g‘ri to‘lov: renewal mavjud muddatga qo‘shiladi (1 + 3 = 4 kun)
    T::send(payUpdate($u, $o2['id'], 60, 'CHARGE-6'));
    $until2 = strtotime(T::user($u)['premium_until'] . ' UTC');
    T::ok(abs($until2 - (strtotime($until1 . ' UTC') + 3 * 86400)) < 5, 'yangi xarid mavjud tugash vaqtiga qo‘shildi');
    // Paid order ga boshqa charge
    T::send(payUpdate($u, $o2['id'], 60, 'CHARGE-7'));
    T::eq($db->val('SELECT reason FROM tb_rejected_payments ORDER BY id DESC LIMIT 1'), 'order_already_paid', 'paid order ga yangi charge rad');
    T::eq(strtotime(T::user($u)['premium_until'] . ' UTC'), $until2, 'ikkinchi marta qo‘shilmadi');
    // Charge ID unique indeksi
    $dup = false;
    try {
        $db->exec("UPDATE tb_orders SET telegram_payment_charge_id = 'CHARGE-6' WHERE id = ?", [$o1['id']]);
    } catch (\PDOException $e) {
        $dup = \TB\Db::isDuplicate($e);
    }
    T::ok($dup, 'charge ID UNIQUE indeks');
});

$t('stars: boost auditoriyasi va premium/boost muddati CRONsiz tugaydi', function () {
    T::isolate();
    $db = App::db();
    $m = 6301;
    T::register($m, 'uz', 'Boostchi', 'm', 7);
    $o = order($m, 'boost', 'f');
    T::send(payUpdate($m, $o['id'], 30, 'BCHARGE-1'));
    $b = $db->one('SELECT * FROM tb_boosts WHERE order_id = ?', [$o['id']]);
    T::eq([$b['audience'], (int)$b['user_id']], ['f', $m], 'boost f auditoriya');
    mkUser(6302, 'm', 1);
    $fv = 6303;
    T::register($fv, 'uz', 'Qiz', 'f', 1);
    T::eq(Search::candidate(T::user($fv) + ['search_pref' => 'm']), $m, 'ayol qidiruvida boostli erkak birinchi (hudud boshqa bo‘lsa ham)');
    $mv = 6304;
    T::register($mv, 'uz', 'Yigit', 'm', 1);
    $db->exec("UPDATE tb_users SET gender='f' WHERE id = ?", [$m]); // faqat filtrlash testi uchun
    T::ok(Search::candidate(T::user($mv) + ['search_pref' => 'm']) !== $m, 'boost jins filtrini chetlab o‘tmaydi');
    $db->exec("UPDATE tb_users SET gender='m' WHERE id = ?", [$m]);

    // Muddat tugashi: CRON chaqirilmaydi
    $db->exec('UPDATE tb_boosts SET expires_at = UTC_TIMESTAMP() - INTERVAL 1 SECOND WHERE order_id = ?', [$o['id']]);
    T::ok(Search::candidate(T::user($fv) + ['search_pref' => 'm']) !== $m, 'tugagan boost ustuvorlik bermaydi (CRONsiz)');
    $db->exec('UPDATE tb_users SET premium_until = UTC_TIMESTAMP() - INTERVAL 1 SECOND WHERE id = ?', [$m]);
    $u = T::user($m);
    T::ok(!Users::isPremium($u), 'tugagan Premium faol emas (CRONsiz)');
    T::eq(Limits::caps($u), ['like' => 30, 'super' => 1], 'bepul limitlar qaytdi');
    $db->exec('UPDATE tb_users SET premium_until = UTC_TIMESTAMP() + INTERVAL 1 HOUR WHERE id = ?', [$m]);
    T::eq(Limits::caps(T::user($m)), ['like' => 300, 'super' => 10], 'premium limitlar');
    T::ok(str_starts_with(\TB\Profile::cardText('uz', T::user($m)), '💎'), 'anketada 💎 belgisi');
    // CRON pending orderlarni expired qiladi
    $o3 = order($m, 'premium_1');
    $db->exec('UPDATE tb_orders SET expires_at = UTC_TIMESTAMP() - INTERVAL 1 MINUTE WHERE id = ?', [$o3['id']]);
    \TB\Cron::run(microtime(true) + 5);
    T::eq($db->val('SELECT status FROM tb_orders WHERE id = ?', [$o3['id']]), 'expired', 'CRON pending orderni expired qildi');
});

$t('webhook: handler o‘rtasida DB xatosi → marker va biznes holati rollback, keyin qayta ishlanadi', function () {
    T::isolate();
    $a = 6401;
    T::register($a, 'uz', 'Rollback', 'm', 1);
    mkUser(6402, 'f', 1);
    T::cb($a, 's:f');
    $nonce = (string)T::user($a)['card_nonce'];
    $db = App::db();
    $upd = T::cbUpdate($a, 'r:l:' . $nonce, false);
    App::$hooks['after_reaction'] = function () {
        throw new \PDOException('simulated DB failure');
    };
    $thrown = false;
    try {
        Bot::handleUpdate($upd);
    } catch (\Throwable $e) {
        $thrown = true;
    }
    App::$hooks = [];
    T::ok($thrown, 'xato tashqariga chiqdi (webhook 500 qaytaradi)');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_processed_updates WHERE update_id = ?', [$upd['update_id']]), 0, 'update marker rollback');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_reactions WHERE from_id = ?', [$a]), 0, 'reaksiya rollback');
    T::eq((int)$db->val('SELECT COALESCE(SUM(likes),0) FROM tb_daily_limits WHERE user_id = ?', [$a]), 0, 'limit rollback');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_outbox WHERE dedupe_key LIKE ?", ['u:' . $upd['update_id'] . ':%']), 0, 'outbox rollback');
    T::eq((string)T::user($a)['card_nonce'], $nonce, 'foydalanuvchi holati rollback');
    $r = T::send($upd);
    T::eq($r['status'], 'ok', 'ayni update keyin muvaffaqiyatli qayta ishlandi');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_reactions WHERE from_id = ?', [$a]), 1, 'reaksiya bir marta yozildi');
    T::eq(T::send($upd)['status'], 'duplicate', 'uchinchi marta no-op');

    // To‘lov o‘rtasida xato
    $o = order($a, 'premium_1');
    $pu = payUpdate($a, $o['id'], 25, 'RB-CHARGE');
    App::$hooks['after_order_paid'] = function () {
        throw new \RuntimeException('crash after paid');
    };
    try {
        Bot::handleUpdate($pu);
    } catch (\Throwable $e) {
    }
    App::$hooks = [];
    T::eq($db->val('SELECT status FROM tb_orders WHERE id = ?', [$o['id']]), 'pending', 'paid holati rollback');
    T::eq(T::user($a)['premium_until'], null, 'xizmat yoqilmadi');
    T::send($pu);
    T::eq($db->val('SELECT status FROM tb_orders WHERE id = ?', [$o['id']]), 'paid', 'qayta urinishda paid');
    T::ok(Users::isPremium(T::user($a)), 'qayta urinishda xizmat yoqildi');
});

$t('webhook: doimiy yiqiladigan update 5 urinishdan keyin o‘tkazib yuboriladi (bot to‘xtab qolmaydi)', function () {
    $u = 6450;
    T::register($u, 'uz', 'Fail', 'm', 1);
    $upd = T::msgUpdate($u, ['text' => '/start']);
    App::$hooks['before_commit'] = function () {
        throw new \RuntimeException('doimiy xato');
    };
    $res = [];
    for ($i = 0; $i < 5; $i++) {
        try {
            $res[] = Bot::handleUpdate($upd)['status'];
        } catch (\Throwable $e) {
            $res[] = 'throw';
        }
    }
    App::$hooks = [];
    T::eq($res, ['throw', 'throw', 'throw', 'throw', 'gave_up'], 'dastlabki 4 marta 500 (Telegram qayta yuboradi), 5-da o‘tkazib yuborildi');
    T::eq(Bot::handleUpdate($upd)['status'], 'duplicate', 'keyin no-op');
});

function parallel(array $updates): array
{
    $procs = [];
    $files = [];
    $start = microtime(true) + 1.5;
    foreach ($updates as $i => $u) {
        $f = tempnam(sys_get_temp_dir(), 'tbupd');
        file_put_contents($f, json_encode($u));
        $files[] = $f;
        $env = array_merge(getenv(), ['TB_CONFIG' => T::$cfgFile]);
        $procs[$i] = proc_open([PHP_BINARY, TB_ROOT . '/tests/worker.php', $f, (string)$start], [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes, null, $env);
        $procs[$i] = [$procs[$i], $pipes];
    }
    $out = [];
    foreach ($procs as $i => [$p, $pipes]) {
        $o = stream_get_contents($pipes[1]);
        $e = stream_get_contents($pipes[2]);
        proc_close($p);
        $j = json_decode((string)$o, true);
        $out[] = ($j['status'] ?? 'raw') . (isset($j['error']) ? '[' . $j['error'] . ']' : '') . ($j ? '' : $o . $e);
    }
    foreach ($files as $f) {
        @unlink($f);
    }
    return $out;
}

$t('parallel: 8 ta PHP worker ayni update va ayni to‘lovni yuborganda xizmat 1 marta yoqiladi', function () {
    $u = 6501;
    T::register($u, 'uz', 'Parallel', 'm', 1);
    $db = App::db();
    $o = order($u, 'premium_7');
    // 1) Ayni update (bir xil update_id) 8 marta
    $upd = payUpdate($u, $o['id'], 120, 'PAR-CHARGE-1');
    $st = parallel(array_fill(0, 8, $upd));
    sort($st);
    T::eq(count(array_filter($st, fn($s) => $s === 'ok')), 1, 'faqat bitta worker ok: ' . implode(',', $st));
    T::eq(count(array_filter($st, fn($s) => $s === 'duplicate')), 7, '7 tasi duplicate');
    $until = strtotime(T::user($u)['premium_until'] . ' UTC');
    T::ok(abs($until - (time() + 7 * 86400)) < 60, 'premium aynan 7 kun (bir marta)');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_orders WHERE status = 'paid' AND user_id = ?", [$u]), 1, 'bitta paid order');

    // 2) Har xil update_id, ayni order va charge
    $o2 = order($u, 'premium_30');
    $ups = [];
    for ($i = 0; $i < 8; $i++) {
        $ups[] = payUpdate($u, $o2['id'], 350, 'PAR-CHARGE-2');
    }
    $before = $until;
    $st2 = parallel($ups);
    T::eq(count(array_filter($st2, fn($s) => $s === 'ok')), 8, 'hamma worker xatosiz tugadi: ' . implode(',', $st2));
    $until2 = strtotime(T::user($u)['premium_until'] . ' UTC');
    T::ok(abs($until2 - ($before + 30 * 86400)) < 5, '30 kun faqat bir marta qo‘shildi');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_rejected_payments WHERE telegram_payment_charge_id = 'PAR-CHARGE-2'"), 0, 'ayni order+charge takrori rad emas, no-op');

    // 3) Ayni charge 8 ta har xil orderga
    $orders = [];
    for ($i = 0; $i < 8; $i++) {
        $orders[] = order($u, 'premium_1');
    }
    $ups = array_map(fn($oo) => payUpdate($u, $oo['id'], 25, 'PAR-CHARGE-3'), $orders);
    $before = $until2;
    $st3 = parallel($ups);
    $paid = (int)$db->val("SELECT COUNT(*) FROM tb_orders WHERE telegram_payment_charge_id = 'PAR-CHARGE-3'");
    T::eq($paid, 1, 'bitta charge faqat bitta orderni yopdi: ' . implode(',', $st3));
    $until3 = strtotime(T::user($u)['premium_until'] . ' UTC');
    T::ok(abs($until3 - ($before + 86400)) < 5, 'xizmat faqat bir marta (+1 kun)');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_rejected_payments WHERE telegram_payment_charge_id = 'PAR-CHARGE-3' AND reason = 'charge_reused'"), 7, '7 ta reuse rad etildi: ' . implode(',', $st3));

    // 4) Oddiy update (like) 8 parallel worker
    T::isolate();
    mkUser(6599, 'f', 1);
    $db->exec("UPDATE tb_users SET status='active' WHERE id = ?", [$u]);
    T::cb($u, 's:f');
    $lk = T::cbUpdate($u, 'r:l:' . T::user($u)['card_nonce'], false);
    $st4 = parallel(array_fill(0, 8, $lk));
    T::eq(count(array_filter($st4, fn($s) => $s === 'ok')), 1, 'like update faqat bir marta: ' . implode(',', $st4));
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_reactions WHERE from_id = ? AND to_id = 6599", [$u]), 1, 'bitta reaksiya');
    T::eq((int)$db->val('SELECT likes FROM tb_daily_limits WHERE user_id = ? AND day = UTC_DATE()', [$u]), 1, 'limit bir marta');
});
