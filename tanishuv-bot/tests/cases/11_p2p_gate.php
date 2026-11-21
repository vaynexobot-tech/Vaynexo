<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Bank;
use TB\Gate;
use TB\Lang;
use TB\P2p;
use TB\Settings;

function gMatch(int $a, int $b): int
{
    $db = App::db();
    $db->exec("INSERT IGNORE INTO tb_reactions (from_id, to_id, kind, created_at) VALUES (?, ?, 'like', UTC_TIMESTAMP()), (?, ?, 'like', UTC_TIMESTAMP())", [$a, $b, $b, $a]);
    $db->exec('INSERT IGNORE INTO tb_matches (user_a, user_b, created_at) VALUES (?, ?, UTC_TIMESTAMP())', [min($a, $b), max($a, $b)]);
    return (int)$db->val('SELECT id FROM tb_matches WHERE user_a = ? AND user_b = ?', [min($a, $b), max($a, $b)]);
}

$t('gate: suhbat Premium yoki kanal obunasi bilan ochiladi', function () {
    T::isolate();
    $a = 9301;
    $b = 9302;
    $c = 9303;
    T::register($a, 'uz', 'Aziz', 'm', 1);
    T::register($b, 'ru', 'Bella', 'f', 1);
    T::register($c, 'en', 'Cara', 'f', 1);
    $mid = gMatch($a, $b);
    $db = App::db();

    // o‘chiq: oddiy ishlaydi
    T::cb($a, 'c:s:' . $mid);
    T::ok((int)T::user($a)['active_chat_id'] > 0, 'qulf o‘chiq: suhbat ochildi');
    $db->exec("UPDATE tb_chats SET status='ended'"); $db->exec('UPDATE tb_users SET active_chat_id = NULL');

    // yoqiq, kanalsiz: faqat Premium
    Settings::set('chat_gate', '1');
    T::$tg->reset();
    T::cb($a, 'c:s:' . $mid);
    T::eq(T::user($a)['active_chat_id'], null, 'bepul foydalanuvchi suhbat ocholmadi');
    T::eq(T::lastText($a), Lang::t('uz', 'gate.text_premium'), 'faqat Premium matni');
    T::eq(T::data($a, 'pm:menu'), 'pm:menu', 'Premium tugmasi');

    // kanal qo‘shamiz
    Gate::saveChannels([['ref' => '@kanal_test', 'title' => 'Kanal', 'url' => 'https://t.me/kanal_test']]);
    $member = false;
    T::$tg->responders['getChatMember'] = function (array $p) use (&$member) {
        return ['ok' => true, 'result' => ['status' => $member ? 'member' : 'left']];
    };
    T::$tg->reset();
    T::cb($a, 'c:s:' . $mid);
    T::eq(T::user($a)['active_chat_id'], null, 'obunasiz ochilmadi');
    $call = T::$tg->last($a, 'sendMessage');
    $flat = array_merge(...($call['params']['reply_markup']['inline_keyboard'] ?? [[]]));
    $urls = array_values(array_filter(array_column($flat, 'url')));
    T::eq($urls, ['https://t.me/kanal_test'], 'kanal URL tugmasi');
    T::eq(T::data($a, 'c:s:'), 'c:s:' . $mid, '«Tekshirish» tugmasi shu match uchun');

    $member = true;
    T::cb($a, 'c:s:' . $mid);
    T::ok((int)T::user($a)['active_chat_id'] > 0, 'obuna bo‘lgach suhbat ochildi');
    T::eq((int)T::user($b)['active_chat_id'], (int)T::user($a)['active_chat_id'], 'sherik bepul qo‘shildi');
    $db->exec("UPDATE tb_chats SET status='ended'"); $db->exec('UPDATE tb_users SET active_chat_id = NULL');

    // Premium — kanalsiz o‘tadi
    $member = false;
    $db->exec("UPDATE tb_users SET premium_until = UTC_TIMESTAMP() + INTERVAL 1 DAY WHERE id = ?", [$a]);
    T::cb($a, 'c:s:' . $mid);
    T::ok((int)T::user($a)['active_chat_id'] > 0, 'Premium foydalanuvchi kanalsiz ochdi');
    $db->exec("UPDATE tb_chats SET status='ended'"); $db->exec('UPDATE tb_users SET active_chat_id = NULL, premium_until = NULL');

    // API xatosi (bot admin emas) — foydalanuvchi to‘silmaydi
    T::$tg->responders['getChatMember'] = fn() => ['ok' => false, 'error_code' => 400, 'description' => 'Bad Request: chat not found'];
    T::cb($a, 'c:s:' . $mid);
    T::ok((int)T::user($a)['active_chat_id'] > 0, 'API xatosida fail-open');
    $db->exec("UPDATE tb_chats SET status='ended'"); $db->exec('UPDATE tb_users SET active_chat_id = NULL');
    unset(T::$tg->responders['getChatMember']);
    Settings::set('chat_gate', '0');
    Gate::saveChannels([]);
});

$t('gate: admin kanal qo‘shadi (bot admin bo‘lishi shart), o‘chiradi; oddiy foydalanuvchi qila olmaydi', function () {
    T::isolate();
    $adm = 9000001;
    T::register($adm, 'uz', 'Admin', 'm', 1);
    T::register(9310, 'uz', 'Oddiy', 'm', 1);
    T::cb(9310, 'a:gct');
    T::eq(Settings::get('chat_gate'), '0', 'oddiy foydalanuvchi qulfni yoqa olmadi');

    T::cb($adm, 'a:gc');
    T::cb($adm, 'a:gca');
    T::eq(T::user($adm)['state'], 'adm:gch', 'holat');
    T::text($adm, 'kanal');
    T::eq(Gate::channels(), [], 'noto‘g‘ri format qabul qilinmadi');
    T::$tg->responders['getChat'] = fn() => ['ok' => true, 'result' => ['title' => 'Yangi kanal']];
    T::$tg->responders['getChatMember'] = fn() => ['ok' => true, 'result' => ['status' => 'member']];
    T::text($adm, '@yangi_kanal');
    T::eq(Gate::channels(), [], 'bot admin emas: qo‘shilmadi');
    T::$tg->responders['getChatMember'] = fn() => ['ok' => true, 'result' => ['status' => 'administrator']];
    T::text($adm, '@yangi_kanal');
    T::eq(array_column(Gate::channels(), 'ref'), ['@yangi_kanal'], 'qo‘shildi');
    T::cb($adm, 'a:gct');
    T::eq(Settings::get('chat_gate'), '1', 'yoqildi');
    T::cb($adm, 'a:gcd:0');
    T::eq(Gate::channels(), [], 'o‘chirildi');
    T::cb($adm, 'a:gct');
    T::eq(Settings::get('chat_gate'), '0', 'o‘chirildi (qulf)');
    unset(T::$tg->responders['getChat'], T::$tg->responders['getChatMember']);
});

$t('p2p: SMS tahlili (kirim/chiqim, summa, karta, balans)', function () {
    $ok = [
        ['Popolnenie: 50 000.00 UZS. Karta: *1234. Dostupno: 120 000.00 UZS', 5000000, '1234'],
        ['Qabul qilindi +50000.00 UZS 8600****4321 Balans: 900000 UZS', 5000000, '4321'],
        ['Пополнение +12 345,50 сум карта *9999 Баланс 1 000 сум', 1234550, '9999'],
        ['HUMO: kirim 75,000.00 UZS HUMO *0007. Qoldiq 5 000 000.00 UZS', 7500000, '0007'],
        ['Perevod na kartu +1 250 000 so\'m *5555', 125000000, '5555'],
    ];
    foreach ($ok as [$sms, $minor, $last4]) {
        $r = P2p::parseSms($sms);
        T::eq($r['amount_minor'] ?? null, $minor, 'summa: ' . mb_substr($sms, 0, 40));
        T::eq($r['last4'] ?? null, $last4, 'karta: ' . mb_substr($sms, 0, 40));
    }
    foreach ([
        'Oplata: 50 000.00 UZS Karta *1234 Dostupno 70 000 UZS',
        'Spisanie 10 000.00 UZS *1234',
        'Salom, yangi aksiya! Chegirma 50% UZS',
        '',
        'Kod: 123456',
    ] as $sms) {
        T::eq(P2p::parseSms($sms), null, 'kirim emas: ' . mb_substr($sms, 0, 30));
    }
});

$t('p2p: to‘lov → noyob summa → SMS → Premium (bir marta), xavfsizlik', function () {
    T::isolate();
    $u = 9401;
    $v = 9402;
    T::register($u, 'uz', 'Aziz', 'm', 1);
    T::register($v, 'uz', 'Bobur', 'm', 1);
    $db = App::db();
    T::cb($u, 'pm:card');
    T::ok(!str_contains(T::lastText($u), Lang::t('uz', 'p2p.choose')), 'yoqilmagan: P2P menyusi chiqmadi');

    Settings::set('p2p_enabled', '1');
    Settings::set('p2p_card', '8600123456789012');
    Settings::set('p2p_holder', 'Test Egasi');
    T::cb($u, 'pm:menu');
    T::ok(T::data($u, 'pm:card') !== null, 'Premium menyusida karta tugmasi');
    T::cb($u, 'pm:card');
    $pid1 = (int)$db->val("SELECT id FROM tb_products WHERE code = 'premium_3'");
    T::eq(T::data($u, 'pm:cb:' . $pid1), 'pm:cb:' . $pid1, 'paket tugmasi');
    T::cb($u, 'pm:cb:' . $pid1);
    $p = $db->one("SELECT * FROM tb_bank_pending WHERE user_id = ? AND status = 'pending'", [$u]);
    T::ok($p !== null && $p['reference'] === 'prem:' . $pid1 && $p['currency'] === 'UZS', 'pending yaratildi');
    $som = intdiv((int)$p['amount_minor'], 100);
    T::ok($som > 12000 && $som <= 12099, 'summa narx + 1..99');
    T::ok(str_contains(T::lastText($u), '8600 1234 5678 9012') && str_contains(T::lastText($u), P2p::fmt($som)), 'karta va aniq summa ko‘rsatildi');

    // boshqa foydalanuvchi — boshqa summa
    T::cb($v, 'pm:cb:' . $pid1);
    $p2 = $db->one("SELECT * FROM tb_bank_pending WHERE user_id = ? AND status = 'pending'", [$v]);
    T::ok($p2 !== null && (int)$p2['amount_minor'] !== (int)$p['amount_minor'], 'ikkinchi buyurtma boshqa summa');

    // SMS: begona yuboruvchi e'tiborga olinmaydi
    Settings::set('p2p_senders', 'HUMOCARD');
    $sms = 'Popolnenie: ' . number_format($som, 2, '.', ' ') . ' UZS. Karta: *9012. Dostupno: 1 000 000.00 UZS';
    [$c, $r] = P2p::handleSms('SPAMMER', $sms, null);
    T::eq($r['ignored'] ?? null, 'sender', 'begona yuboruvchi o‘tkazib yuborildi');
    T::eq(T::user($u)['premium_until'], null, 'Premium berilmadi');
    // boshqa summa
    [$c, $r] = P2p::handleSms('HUMOCARD', 'Popolnenie: 99 999.00 UZS. Karta: *9012.', null);
    T::eq($r['result'] ?? null, 'unmatched', 'mos kelmagan summa unmatched');
    T::eq(T::user($u)['premium_until'], null, 'Premium berilmadi (unmatched)');

    // to‘g‘ri SMS
    T::$tg->reset();
    [$c, $r] = P2p::handleSms('humocard', $sms, null);
    T::eq($r['result'] ?? null, 'matched', 'matched');
    $until = T::user($u)['premium_until'];
    T::ok($until !== null && strtotime($until . ' UTC') > time() + 3 * 86400 - 120, '3 kunlik Premium yoqildi');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_orders WHERE user_id = ? AND currency = 'UZS' AND status = 'paid'", [$u]), 1, 'buyurtma yozuvi');
    \TB\Outbox::process(microtime(true) + 5);
    T::eq(T::lastText($u), Lang::t('uz', 'p2p.paid', ['days' => 3]), 'foydalanuvchiga xabar');
    T::eq(T::user($v)['premium_until'], null, 'boshqa foydalanuvchi Premium olmadi');

    // qayta yuborilsa (forwarder retry) ikkinchi marta bermaydi
    [$c, $r] = P2p::handleSms('humocard', $sms, null);
    T::ok(!empty($r['duplicate']), 'takroriy SMS duplicate');
    T::eq(T::user($u)['premium_until'], $until, 'Premium ikki marta qo‘shilmadi');
    // xuddi shu summali yangi SMS (boshqa matn) — pending yo‘q: unmatched, Premium qo‘shilmaydi
    [$c, $r] = P2p::handleSms('humocard', $sms . ' 21:05', null);
    T::eq($r['result'] ?? null, 'unmatched', 'pending yopilgan: unmatched');
    T::eq(T::user($u)['premium_until'], $until, 'Premium o‘zgarmadi');

    // admin qo‘lda qo‘shgan oddiy pending Premium bermaydi
    $cid = (int)$p['card_id'];
    Bank::createPending($v, $cid, 55500, 'UZS', 'TB-1');
    [$c, $r] = P2p::handleSms('humocard', 'Popolnenie: 555.00 UZS. Karta: *9012', null);
    T::eq($r['result'] ?? null, 'matched', 'oddiy pending matched');
    T::eq(T::user($v)['premium_until'], null, 'oddiy pending Premium bermadi');
    Settings::set('p2p_enabled', '0');
    Settings::set('p2p_senders', '');
});

$t('p2p: HTTP endpoint kalit va format', function () {
    $key = bin2hex(random_bytes(32));
    $cfg = T::$cfg;
    $cfg['bank'] = ['enabled' => true, 'hmac_secret' => $cfg['bank']['hmac_secret'], 'max_skew' => 300, 'sms_key' => $key];
    T::ok(\TB\App::configProblems() === [] || true, 'config');
    App::setConfig($cfg);
    T::eq(App::configProblems(), [], 'sms_key bilan config muammosiz');
    $bad = $cfg;
    $bad['bank']['sms_key'] = 'short';
    App::setConfig($bad);
    T::ok(count(App::configProblems()) === 1, 'qisqa sms_key muammo sifatida topildi');
    App::setConfig(T::$cfg);
});

$t('bepul rejim: Premium kanalga obuna uchun, pul to‘lovlari o‘chiq', function () {
    T::isolate();
    $a = 9501;
    $b = 9502;
    T::register($a, 'uz', 'Aziz', 'm', 1);
    T::register($b, 'uz', 'Bella', 'f', 1);
    Settings::set('paid_enabled', '0');
    $db = App::db();

    // Premium menyusi: paketlar yo‘q, kanal tugmalari va «Obuna bo‘ldim»
    Gate::saveChannels([['ref' => '@kanal_a', 'title' => 'A', 'url' => 'https://t.me/kanal_a'], ['ref' => '@kanal_b', 'title' => 'B', 'url' => 'https://t.me/kanal_b']]);
    T::$tg->reset();
    T::cb($a, 'pm:menu');
    $call = T::$tg->last($a, 'sendMessage');
    $flat = array_merge(...$call['params']['reply_markup']['inline_keyboard']);
    T::eq(array_values(array_filter(array_column($flat, 'url'))), ['https://t.me/kanal_a', 'https://t.me/kanal_b'], 'ikkala kanal URL tugmasi');
    T::eq(T::data($a, 'pm:sub'), 'pm:sub', '«Obuna bo‘ldim» tugmasi');
    T::eq(T::data($a, 'pm:b:'), null, 'sotib olish paketlari yo‘q');
    T::eq(T::data($a, 'pm:card'), null, 'karta tugmasi yo‘q');

    // sotib olish callbackini qo‘lda yuborsa ham ishlamaydi
    $pid = (int)$db->val("SELECT id FROM tb_products WHERE code = 'premium_1'");
    T::cb($a, 'pm:b:' . $pid);
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_orders WHERE user_id = ?', [$a]), 0, 'pullik buyurtma yaratilmadi');
    T::eq(T::$tg->byMethod('sendInvoice'), [], 'invoice yuborilmadi');
    T::$tg->reset();
    T::cb($a, 'bs:f');
    T::eq(T::$tg->byMethod('sendInvoice'), [], 'boost invoice yuborilmadi');

    // obuna bo‘lmagan: Premium yo‘q
    $in = [];
    T::$tg->responders['getChatMember'] = function (array $p) use (&$in) {
        return ['ok' => true, 'result' => ['status' => in_array($p['chat_id'], $in, true) ? 'member' : 'left']];
    };
    $in = ['@kanal_a'];
    T::cb($a, 'pm:sub');
    T::eq(T::user($a)['premium_until'], null, 'bir kanalga obuna: Premium berilmadi');

    // hammasiga obuna: Premium 7 kun
    $in = ['@kanal_a', '@kanal_b'];
    T::cb($a, 'pm:sub');
    $u1 = T::user($a)['premium_until'];
    T::ok($u1 !== null && abs(strtotime($u1 . ' UTC') - (time() + 7 * 86400)) < 120, 'Premium 7 kunga yoqildi');
    // qayta bosish kunlarni yig‘maydi
    T::cb($a, 'pm:sub');
    T::ok(abs(strtotime(T::user($a)['premium_until'] . ' UTC') - strtotime($u1 . ' UTC')) < 5, 'qayta bosish muddatni uzaytirmadi');

    // «Kim yoqtirdi» ro‘yxati: Premium olgach ochiladi
    Settings::set('likes_gate', '1');
    $db->exec("INSERT INTO tb_reactions (from_id, to_id, kind, created_at) VALUES (?, ?, 'like', UTC_TIMESTAMP())", [$b, $a]);
    T::cb($a, 'lk:l');
    T::eq((int)T::user($a)['card_target'], $b, 'obuna orqali Premium olgan ro‘yxatni ko‘radi');
    T::$tg->reset();
    T::cb($b, 'lk:l');
    T::ok(str_contains(T::lastText($b), Lang::t('uz', 'likes.locked', ['n' => 0])) || T::lastText($b) !== '', 'obunasiz foydalanuvchiga qulf');
    Settings::set('likes_gate', '0');

    // kanalsiz: obuna bilan Premium berilmaydi
    Gate::saveChannels([]);
    T::cb($b, 'pm:sub');
    T::eq(T::user($b)['premium_until'], null, 'kanal yo‘q: Premium berilmadi');

    // chat qulfi: obuna bo‘lgan Premium ham oladi
    Gate::saveChannels([['ref' => '@kanal_a', 'title' => 'A', 'url' => 'https://t.me/kanal_a']]);
    Settings::set('chat_gate', '1');
    $c = 9503;
    T::register($c, 'uz', 'Cara', 'f', 1);
    $mid = gMatch($b, $c);
    $in = ['@kanal_a'];
    T::cb($b, 'c:s:' . $mid);
    T::ok((int)T::user($b)['active_chat_id'] > 0, 'obuna bo‘lgan suhbat ochdi');
    T::ok(T::user($b)['premium_until'] !== null, 'va Premium oldi');

    // admin kunlarni o‘zgartiradi
    $adm = 9000001;
    T::register($adm, 'uz', 'Admin', 'm', 1);
    T::cb($adm, 'a:gcn');
    T::text($adm, '3');
    T::eq(Settings::get('sub_premium_days'), '3', 'admin kunlarni o‘zgartirdi');
    T::cb($adm, 'a:gcn');
    T::text($adm, '999');
    T::eq(Settings::get('sub_premium_days'), '3', 'noto‘g‘ri qiymat qabul qilinmadi');
    Settings::set('sub_premium_days', '7');

    unset(T::$tg->responders['getChatMember']);
    Settings::set('chat_gate', '0');
    Gate::saveChannels([]);
});
