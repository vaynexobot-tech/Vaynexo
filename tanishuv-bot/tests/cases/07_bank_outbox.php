<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Bank;
use TB\Outbox;

function bankSend(array $body, ?string $secret = null, ?int $ts = null, ?string $raw = null): array
{
    $raw ??= json_encode($body);
    $ts ??= time();
    $secret ??= (string)App::cfg('bank.hmac_secret');
    return Bank::handle($raw, (string)$ts, Bank::sign($secret, (string)$ts, $raw));
}

function ev(array $o = []): array
{
    static $n = 0;
    $n++;
    return $o + ['source' => 'sms_gateway', 'event_id' => 'ev-' . $n . '-' . bin2hex(random_bytes(3)), 'test' => false, 'amount_minor' => 1500000, 'currency' => 'UZS', 'card_last4' => '1234', 'reference' => null, 'occurred_at' => gmdate('c')];
}

$t('bank: 20 ta karta, bir kartada bir nechta pending, faqat **** 1234', function () {
    $db = App::db();
    for ($i = 1; $i <= 20; $i++) {
        Bank::addCard('Karta ' . $i, str_pad((string)(1000 + $i), 4, '0', STR_PAD_LEFT));
    }
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_cards'), 20, '20 ta karta qo‘shildi (18 limit yo‘q)');
    // Admin oqimi: to‘liq raqam saqlanmaydi
    T::cb(9000001, 'a:bka');
    T::text(9000001, 'Asosiy karta');
    T::text(9000001, '8600 1234 5678 9012');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_cards'), 20, 'to‘liq karta raqami rad etildi');
    T::text(9000001, '9012');
    T::eq($db->val('SELECT last4 FROM tb_cards ORDER BY id DESC LIMIT 1'), '9012', 'faqat oxirgi 4 raqam');
    $cols = array_column($db->all('SHOW COLUMNS FROM tb_cards'), 'Field');
    T::eq($cols, ['id', 'title', 'last4', 'active', 'created_at'], 'kartalar jadvalida PIN/CVV/to‘liq raqam ustuni yo‘q');
    $card = (int)$db->val("SELECT id FROM tb_cards WHERE last4 = '1001'");
    $p1 = Bank::createPending(111, $card, 500000, 'UZS', null);
    $p2 = Bank::createPending(112, $card, 700000, 'UZS', null);
    $p3 = Bank::createPending(113, $card, 900000, 'UZS', 'TB-REF-1');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_bank_pending WHERE card_id = ? AND status='pending'", [$card]), 3, 'bitta kartada 3 ta pending');
    $cols = array_column($db->all('SHOW COLUMNS FROM tb_bank_pending'), 'Field');
    foreach (['user_id', 'card_id', 'amount_minor', 'currency', 'reference', 'created_at', 'expires_at', 'status'] as $c) {
        T::ok(in_array($c, $cols, true), "pending ustuni: $c");
    }
    T::cb(9000001, 'a:bkc:0');
    T::ok(str_contains(T::lastText(9000001), '21'), 'admin kartalar ro‘yxati');
});

$t('bank: HMAC, timestamp, test event, duplicate, ambiguous, reference, unmatched', function () {
    $db = App::db();
    $db->deleteSetting('bank_connected_at');
    $card = (int)$db->val("SELECT id FROM tb_cards WHERE last4 = '1002'");
    $pA = Bank::createPending(201, $card, 2500000, 'UZS', null);
    $pB = Bank::createPending(202, $card, 2500000, 'UZS', null); // xuddi shu summa → ambiguous
    $pC = Bank::createPending(203, $card, 3300000, 'UZS', null);
    $pR = Bank::createPending(204, $card, 2500000, 'UZS', 'TB-EXACT-77');

    // Imzo
    [$c] = bankSend(ev(), 'wrong-secret-wrong-secret-wrong-secret-00');
    T::eq($c, 401, 'noto‘g‘ri imzo 401');
    $raw = json_encode(ev());
    $ts = (string)time();
    [$c] = Bank::handle($raw, $ts, Bank::sign((string)App::cfg('bank.hmac_secret'), $ts, $raw . ' '));
    T::eq($c, 401, 'body o‘zgarsa imzo yaroqsiz');
    [$c, $b] = bankSend(ev(), null, time() - 301);
    T::eq([$c, $b['error']], [401, 'timestamp_skew'], 'timestamp 301 s farq rad');
    [$c] = bankSend(ev(), null, time() - 290);
    T::eq($c, 200, 'timestamp 290 s farq qabul');
    [$c] = Bank::handle($raw, $ts, null);
    T::eq($c, 401, 'imzosiz rad');
    [$c, $b] = bankSend([], null, null, '{bad json');
    T::eq([$c, $b['error']], [400, 'invalid_json'], 'noto‘g‘ri JSON');
    [$c, $b] = bankSend(ev(['amount_minor' => '100']));
    T::eq([$c, $b['field'] ?? ''], [422, 'amount_minor'], 'format tekshiruvi');
    [$c] = bankSend(ev(['card_last4' => '8600123412341234']));
    T::eq($c, 422, 'to‘liq karta raqami qabul qilinmaydi');
    $db->deleteSetting('bank_connected_at');
    $events0 = (int)$db->val('SELECT COUNT(*) FROM tb_bank_events');

    // test=true: imzo+format, DB ga yozmaydi, pending ni yopmaydi, Ulangan ni yoqmaydi
    [$c, $b] = bankSend(ev(['test' => true, 'amount_minor' => 3300000]));
    T::eq([$c, $b['test'] ?? null], [200, true], 'test event qabul');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_bank_events'), $events0, 'test event DB ga yozilmadi');
    T::eq($db->val('SELECT status FROM tb_bank_pending WHERE id = ?', [$pC]), 'pending', 'test event pendingni yopmadi');
    T::eq($db->setting('bank_connected_at'), null, 'test event "Ulangan" ni yoqmadi');
    [$c] = bankSend(ev(['test' => true]), 'bad-secret-bad-secret-bad-secret-bad-secret');
    T::eq($c, 401, 'test event ham imzo talab qiladi');
    T::cb(9000001, 'a:bks');
    T::ok(str_contains(T::lastText(9000001), '⛔'), 'admin: "Ulanmagan"');

    // Bitta aniq moslik
    $e1 = ev(['amount_minor' => 3300000, 'card_last4' => '1002']);
    [$c, $b] = bankSend($e1);
    T::eq([$c, $b['result'], $b['pending_id']], [200, 'matched', $pC], 'bitta moslik → matched');
    T::eq($db->val('SELECT status FROM tb_bank_pending WHERE id = ?', [$pC]), 'matched', 'pending yopildi');
    T::ok($db->setting('bank_connected_at') !== null, 'haqiqiy event "Ulangan" ni yoqdi');
    // Duplicate
    [$c, $b] = bankSend($e1);
    T::eq([$c, $b['duplicate'] ?? false], [200, true], 'takroriy event');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_bank_events WHERE event_id = ?', [$e1['event_id']]), 1, 'ikki marta hisoblanmadi');
    // Ambiguous (pA, pB, pR bir xil summa, bir karta)
    [$c, $b] = bankSend(ev(['amount_minor' => 2500000, 'card_last4' => '1002']));
    T::eq([$b['result'], $b['pending_id']], ['ambiguous', null], 'bir nechta moslik → ambiguous');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_bank_pending WHERE id IN (?, ?, ?) AND status = 'pending'", [$pA, $pB, $pR]), 3, 'ambiguous hech biriga biriktirilmadi');
    // Reference bo‘yicha aniq
    [$c, $b] = bankSend(ev(['amount_minor' => 2500000, 'card_last4' => '1002', 'reference' => 'TB-EXACT-77']));
    T::eq([$b['result'], $b['pending_id']], ['matched', $pR], 'reference bo‘yicha aynan moslik');
    T::eq($db->val('SELECT status FROM tb_bank_pending WHERE id = ?', [$pA]), 'pending', 'boshqa pending tegilmadi');
    // Noto‘g‘ri reference
    [$c, $b] = bankSend(ev(['amount_minor' => 2500000, 'reference' => 'NOPE']));
    T::eq($b['result'], 'unmatched', 'reference topilmasa unmatched');
    // Nol moslik
    [$c, $b] = bankSend(ev(['amount_minor' => 999, 'card_last4' => '1002']));
    T::eq($b['result'], 'unmatched', 'nol moslik → unmatched');
    // Bank kirimi Premium yoki boost bermaydi
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_users WHERE id IN (201,202,203,204) AND premium_until IS NOT NULL'), 0, 'bank kirimi Premium yoqmadi');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_boosts WHERE user_id IN (201,202,203,204)'), 0, 'bank kirimi boost yoqmadi');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_orders WHERE user_id IN (201,202,203,204)"), 0, 'Stars hisobiga aralashmadi');
    // Body limiti
    [$c] = Bank::handle(str_repeat('x', 32769), (string)time(), 'x');
    T::eq($c, 413, 'bank body 32 KiB dan katta → 413');
    // O‘chiq bo‘lsa
    $cfg = T::$cfg;
    $cfg['bank']['enabled'] = false;
    App::setConfig($cfg);
    [$c] = bankSend(ev());
    T::eq($c, 503, 'integratsiya o‘chiq bo‘lsa 503');
    App::setConfig(T::$cfg);
});

$t('outbox: dedupe, 429 retry_after, backoff, payload {} bilan tozalanadi', function () {
    $db = App::db();
    T::eq(Outbox::add(1, 'sendMessage', ['chat_id' => 1, 'text' => 'a'], 'dd-1') !== null, true, 'birinchi qo‘shildi');
    T::eq(Outbox::add(1, 'sendMessage', ['chat_id' => 1, 'text' => 'a'], 'dd-1'), null, 'dedupe: ikkinchisi qo‘shilmadi');
    $calls = 0;
    T::$tg->responders['sendMessage'] = function ($p) use (&$calls) {
        $calls++;
        if (($p['text'] ?? '') === 'flood') {
            return ['ok' => false, 'error_code' => 429, 'description' => 'Too Many Requests', 'parameters' => ['retry_after' => 7]];
        }
        if (($p['text'] ?? '') === 'temp') {
            return ['ok' => false, 'error_code' => 502, 'description' => 'Bad Gateway'];
        }
        if (($p['text'] ?? '') === 'blocked') {
            return ['ok' => false, 'error_code' => 403, 'description' => 'Forbidden: bot was blocked by the user'];
        }
        return ['ok' => true, 'result' => []];
    };
    $db->exec("DELETE FROM tb_outbox WHERE status IN ('pending','sending')");
    $f = Outbox::add(2, 'sendMessage', ['chat_id' => 2, 'text' => 'flood'], 'dd-flood');
    $tmp = Outbox::add(3, 'sendMessage', ['chat_id' => 3, 'text' => 'temp'], 'dd-temp');
    $bl = Outbox::add(4, 'sendMessage', ['chat_id' => 4, 'text' => 'blocked'], 'dd-block');
    Outbox::process(microtime(true) + 5, 100, [$f]);
    $r = $db->one('SELECT *, TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), next_attempt_at) AS wait FROM tb_outbox WHERE id = ?', [$f]);
    T::eq($r['status'], 'pending', '429 → pending');
    T::ok((int)$r['wait'] >= 5 && (int)$r['wait'] <= 7, '429 retry_after hisobga olindi (' . $r['wait'] . ' s)');
    Outbox::process(microtime(true) + 5, 100, [$tmp]);
    $r = $db->one('SELECT *, TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), next_attempt_at) AS wait FROM tb_outbox WHERE id = ?', [$tmp]);
    T::eq([$r['status'], (int)$r['attempts']], ['pending', 1], 'vaqtinchalik xato → qayta urinish');
    T::ok((int)$r['wait'] >= 8, 'backoff (' . $r['wait'] . ' s)');
    for ($i = 0; $i < 10; $i++) {
        $db->exec('UPDATE tb_outbox SET next_attempt_at = UTC_TIMESTAMP() WHERE id = ?', [$tmp]);
        Outbox::process(microtime(true) + 5, 100, [$tmp]);
    }
    $r = $db->one('SELECT * FROM tb_outbox WHERE id = ?', [$tmp]);
    T::eq([$r['status'], $r['payload']], ['failed', '{}'], '8 urinishdan keyin failed va payload {}');
    T::eq((int)$r['attempts'], Outbox::MAX_ATTEMPTS, 'urinishlar soni');
    Outbox::process(microtime(true) + 5, 100, [$bl]);
    $r = $db->one('SELECT * FROM tb_outbox WHERE id = ?', [$bl]);
    T::eq([$r['status'], $r['payload']], ['failed', '{}'], '403 → uzil-kesil failed, payload {}');
    $db->exec("UPDATE tb_outbox SET next_attempt_at = UTC_TIMESTAMP() WHERE id = ?", [$f]);
    T::$tg->responders['sendMessage'] = fn() => ['ok' => true, 'result' => []];
    Outbox::process(microtime(true) + 5, 100, [$f]);
    T::eq($db->one('SELECT status, payload FROM tb_outbox WHERE id = ?', [$f]), ['status' => 'sent', 'payload' => '{}'], 'yuborilgan → sent, payload {}');
    unset(T::$tg->responders['sendMessage']);
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_outbox WHERE status IN ('sent','failed') AND payload <> '{}'"), 0, 'yuborilgan/rad etilgan payloadlar tozalangan');
});

$t('lock: GET_LOCK nomi baza nomiga bog‘langan va 64 belgidan oshmaydi', function () {
    $n = App::db()->lockName('cron');
    T::ok(str_starts_with($n, 'tb') && strlen($n) <= 64, 'lock nomi: ' . $n);
    T::ok(\TB\Db::lockPrefixFor('boshqa_baza') . 'cron' !== $n, 'boshqa baza uchun boshqa lock nomi');
});

$t('delete: /delete profil, rasm file_id, reaksiyalarni o‘chiradi; to‘lov yozuvlari qoladi', function () {
    $u = 7001;
    T::register($u, 'uz', 'Ketuvchi', 'm', 1);
    $db = App::db();
    $db->exec("INSERT INTO tb_reactions (from_id, to_id, kind, created_at) VALUES (?, 1001, 'like', UTC_TIMESTAMP()), (1002, ?, 'save', UTC_TIMESTAMP())", [$u, $u]);
    $db->exec("INSERT INTO tb_orders (id, user_id, product_id, kind, days, amount, currency, status, created_at, expires_at) VALUES (?, ?, 1, 'premium', 1, 25, 'XTR', 'paid', UTC_TIMESTAMP(), UTC_TIMESTAMP())", [bin2hex(random_bytes(16)), $u]);
    T::text($u, '/delete');
    T::eq(T::user($u)['reg_step'], 'done', 'tasdiqsiz o‘chmadi');
    T::cb($u, 'del:yes');
    T::eq(T::user($u), null, 'profil o‘chirildi');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_reactions WHERE from_id = ? OR to_id = ?', [$u, $u]), 0, 'reaksiyalar o‘chirildi');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_orders WHERE user_id = ?', [$u]), 1, 'to‘lov yozuvi saqlandi');
    T::text($u, '/start');
    T::eq(T::user($u)['reg_step'], 'lang', 'qayta /start yangi ro‘yxat');
});

$t('admin: suspend faol suhbatni tugatadi va qidiruvdan chiqaradi', function () {
    $a = 7101;
    $b = 7102;
    T::register($a, 'uz', 'Suspend A', 'm', 1);
    T::register($b, 'uz', 'Suspend B', 'f', 1);
    $mid = makeMatch($a, $b);
    T::cb($a, 'c:s:' . $mid);
    T::cb(9000001, 'a:us:' . $b);
    T::eq(T::user($a)['active_chat_id'], null, 'suhbat tugadi');
    T::eq(T::user($b)['status'], 'suspended', 'suspended');
    T::text($b, '🔍 Suhbatdosh qidirish');
    T::eq(T::lastText($b), \TB\Lang::t('uz', 'err.suspended'), 'suspended foydalanuvchi qidira olmaydi');
});

$t('callback_data: har bir tugma 64 baytdan oshmaydi', function () {
    $max = 0;
    $bad = [];
    foreach (array_unique(T::$allCallbacks) as $d) {
        $max = max($max, strlen($d));
        if (strlen($d) > 64) {
            $bad[] = $d;
        }
    }
    T::eq($bad, [], '64 baytdan uzun callback_data yo‘q');
    T::ok(count(array_unique(T::$allCallbacks)) > 100, 'tekshirilgan noyob callback_data soni: ' . count(array_unique(T::$allCallbacks)) . ', eng uzuni ' . $max . ' bayt');
    $thrown = false;
    try {
        \TB\Kb::inline([[['x', str_repeat('a', 65)]]]);
    } catch (\LogicException $e) {
        $thrown = true;
    }
    T::ok($thrown, 'Kb::inline 65 baytli callbackni rad etadi');
});
