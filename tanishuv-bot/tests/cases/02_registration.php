<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Lang;
use TB\Users;

$t('registration: uch tilda to‘liq ro‘yxatdan o‘tish va bosh menyu tartibi', function () {
    foreach (['uz' => 1001, 'ru' => 1002, 'en' => 1003] as $l => $uid) {
        T::register($uid, $l, 'Ism ' . $l, 'f', 5, ['music', 'travel']);
        $u = T::user($uid);
        T::eq($u['reg_step'], 'done', "$l: reg_step done");
        T::eq((int)$u['age_confirmed'], 1, "$l: 18+ tasdiqlangan");
        T::eq($u['lang'], $l, "$l: til saqlangan");
        T::eq($u['gender'], 'f', "$l: jins");
        T::eq((int)$u['region'], 5, "$l: hudud");
        T::eq(Users::interests($u), ['music', 'travel'], "$l: qiziqishlar");
        T::eq(count(Users::photos($u)), 1, "$l: 1 ta rasm");
        T::eq(T::lastText($uid), Lang::t($l, 'reg.done'), "$l: yakuniy xabar o‘z tilida");
        $kb = T::lastReplyKeyboard($uid);
        $labels = array_map(static fn($row) => array_map(static fn($b) => $b['text'], $row), (array)$kb);
        T::eq($labels, [
            [Lang::t($l, 'menu.search')],
            [Lang::t($l, 'menu.likes')],
            [Lang::t($l, 'menu.profile')],
            [Lang::t($l, 'menu.premium'), Lang::t($l, 'menu.boost')],
        ], "$l: reply keyboard aynan 4 qator tartibda");
    }
    $uzKb = T::lastReplyKeyboard(1001);
    T::eq($uzKb[0][0]['text'], '🔍 Suhbatdosh qidirish', 'UZ 1-qator');
    T::eq($uzKb[3][1]['text'], '🚀 Profilni ko‘tarish', 'UZ 4-qator 2-tugma');
});

$t('registration: har bosqichda /start saqlangan bosqichdan davom etadi', function () {
    $uid = 1100;
    $expect = function (string $key, string $step) use ($uid) {
        T::$tg->reset();
        T::text($uid, '/start');
        T::eq(T::user($uid)['reg_step'], $step, "/start dan keyin bosqich $step o‘zgarmadi");
        T::ok(str_contains(T::lastText($uid), Lang::t('ru', $key, ['min' => 18, 'max' => 99])), "/start $step bosqich savolini qayta yubordi");
    };
    T::text($uid, '/start');
    T::eq(T::user($uid)['reg_step'], 'lang', 'boshlanish: lang');
    T::text($uid, '/start');
    T::ok(str_contains(T::lastText($uid), 'Choose language'), 'lang bosqichida til tanlovi qaytadi');
    T::cb($uid, 'lang:ru');
    $expect('reg.age', 'age');
    T::cb($uid, 'reg:age:yes');
    $expect('reg.agenum', 'agenum');
    T::text($uid, '25');
    $expect('reg.name', 'name');
    T::text($uid, 'Анна');
    $expect('reg.photo_none', 'photo');
    T::photo($uid, 'P1');
    T::text($uid, '/start');
    T::eq(T::user($uid)['reg_step'], 'photo', 'rasm yuklangach /start: photo');
    T::ok(str_contains(T::lastText($uid), '1/5'), 'yuklangan rasm soni eslab qolingan');
    T::cb($uid, 'reg:ph:done');
    $expect('reg.gender', 'gender');
    T::cb($uid, 'reg:g:f');
    $expect('reg.goal', 'goal');
    T::cb($uid, 'reg:gl:serious');
    $expect('reg.region', 'region');
    T::cb($uid, 'reg:r:11');
    $expect('reg.interests', 'interests');
    T::cb($uid, 'reg:i:books');
    T::text($uid, '/start');
    T::eq(Users::interests(T::user($uid)), ['books'], 'tanlangan qiziqish /start dan keyin saqlangan');
    T::cb($uid, 'reg:i:done');
    T::$tg->reset();
    T::text($uid, '/start');
    T::eq(T::user($uid)['reg_step'], 'review', 'review bosqichi saqlangan');
    T::ok(T::data($uid, 'reg:ok') !== null, 'review da Tasdiqlash tugmasi qayta chiqdi');
    T::cb($uid, 'reg:ok');
    T::eq(T::user($uid)['reg_step'], 'done', 'done');
    T::$tg->reset();
    T::text($uid, '/start');
    T::eq(T::lastText($uid), Lang::t('ru', 'menu.welcome_back'), 'tayyor profil bilan /start bosh menyuni ochadi');
    T::ok(T::lastReplyKeyboard($uid) !== null, 'bosh menyu klaviaturasi');
});

$t('registration: 18+ bosqichini soxta callback bilan chetlab o‘tib bo‘lmaydi', function () {
    $uid = 1200;
    T::text($uid, '/start');
    T::cb($uid, 'lang:uz');
    foreach (['reg:g:m', 'reg:r:1', 'reg:i:music', 'reg:i:done', 'reg:ok', 'reg:ph:done', 'reg:ph:tg', 'pr:e:name', 's:a', 'pm:b:1'] as $forged) {
        T::cb($uid, $forged);
    }
    T::text($uid, 'Soxta Ism');
    T::photo($uid, 'HACK');
    $u = T::user($uid);
    T::eq($u['reg_step'], 'age', 'bosqich age da qoldi');
    T::eq((int)$u['age_confirmed'], 0, 'age_confirmed=0');
    T::eq($u['name'], null, 'ism saqlanmadi');
    T::eq($u['gender'], null, 'jins saqlanmadi');
    T::eq($u['photos'], null, 'rasm saqlanmadi');
    T::cb($uid, 'reg:age:no');
    T::eq(T::user($uid)['reg_step'], 'age', '"Yo‘q" bosilganda ham profil ochilmadi');
    T::eq((int)App::db()->val('SELECT COUNT(*) FROM tb_orders WHERE user_id = ?', [$uid]), 0, 'buyurtma ochilmadi');
    // To‘g‘ridan-to‘g‘ri review ga sakrashga urinish: DB da qadamni review ga qo‘yib, age_confirmed=0 holda reg:ok
    App::db()->exec("UPDATE tb_users SET reg_step='review', name='X Y', photos='[\"a\"]', gender='m', region=1, interests='music' WHERE id=?", [$uid]);
    T::cb($uid, 'reg:ok');
    $u = T::user($uid);
    T::eq($u['reg_step'], 'age', 'age_confirmed=0 bo‘lsa reg:ok age bosqichiga qaytaradi');
    T::ok(!Users::isComplete($u), 'profil to‘liq emas');
});

$t('registration: 5 ta foto chegarasi', function () {
    $uid = 1300;
    T::text($uid, '/start');
    T::cb($uid, 'lang:en');
    T::cb($uid, 'reg:age:yes');
    T::text($uid, '25');
    T::text($uid, 'John');
    for ($i = 1; $i <= 6; $i++) {
        T::photo($uid, 'F' . $i);
    }
    T::eq(count(Users::photos(T::user($uid))), 5, 'faqat 5 ta rasm saqlandi');
    T::eq(T::lastText($uid), Lang::t('en', 'err.photo_max', ['max' => 5]), '6-rasmda xato xabari');
    T::eq(Users::photos(T::user($uid))[0], 'F1', 'faqat file_id saqlanadi (eng katta o‘lcham)');
});

$t('registration: Telegram profil rasmi va fallback', function () {
    $a = 1400;
    T::$tg->profilePhotos[$a] = 'TGFILE_A';
    T::text($a, '/start');
    T::cb($a, 'lang:uz');
    T::cb($a, 'reg:age:yes');
    T::text($a, '25');
    T::text($a, 'Alisher');
    $sp = T::$tg->last($a, 'sendPhoto');
    T::eq($sp['params']['photo'] ?? null, 'TGFILE_A', 'Telegram profil rasmi file_id orqali ko‘rsatildi');
    T::ok(T::data($a, 'reg:ph:tg') !== null, '"Shu rasmni ishlatish" tugmasi bor');
    T::cb($a, 'reg:ph:tg', false);
    T::eq(Users::photos(T::user($a)), ['TGFILE_A'], 'profil rasmi file_id saqlandi');
    T::eq(T::user($a)['reg_step'], 'gender', 'keyingi bosqich');

    $b = 1401;
    T::text($b, '/start');
    T::cb($b, 'lang:uz');
    T::cb($b, 'reg:age:yes');
    T::text($b, '25');
    T::$tg->reset();
    T::text($b, 'Bobur');
    T::eq(T::lastText($b), Lang::t('uz', 'reg.photo_none'), 'rasm olinmadi xabari');
    T::ok(T::data($b, 'reg:ph:up') !== null, '"Rasm yuklash" tugmasi chiqdi');
    T::eq(T::data($b, 'reg:ph:tg'), null, 'profil rasmi tugmasi yo‘q');
    T::cb($b, 'reg:ph:tg');
    T::eq(T::user($b)['reg_step'], 'photo', 'soxta reg:ph:tg rad etildi');
    T::cb($b, 'reg:ph:done');
    T::eq(T::user($b)['reg_step'], 'photo', 'rasmsiz Tayyor rad etildi');

    // Telegram API xato qaytarsa ham fallback
    $c = 1402;
    T::$tg->responders['getUserProfilePhotos'] = fn() => ['ok' => false, 'error_code' => 0, 'description' => 'network'];
    T::text($c, '/start');
    T::cb($c, 'lang:uz');
    T::cb($c, 'reg:age:yes');
    T::text($c, '25');
    T::text($c, 'Cmil');
    T::ok(T::data($c, 'reg:ph:up') !== null, 'tarmoq xatosida ham "Rasm yuklash"');
    unset(T::$tg->responders['getUserProfilePhotos']);
});

$t('registration: ism uzunligi 2–40', function () {
    $uid = 1500;
    T::text($uid, '/start');
    T::cb($uid, 'lang:uz');
    T::cb($uid, 'reg:age:yes');
    T::text($uid, '25');
    T::text($uid, 'A');
    T::eq(T::user($uid)['name'], null, '1 belgi rad');
    T::text($uid, str_repeat('Я', 41));
    T::eq(T::user($uid)['name'], null, '41 belgi rad');
    T::text($uid, str_repeat('Я', 40));
    T::eq(T::user($uid)['name'], str_repeat('Я', 40), '40 belgi (multibyte) qabul');
});

$t('registration: tasdiqlangach ro‘yxat xabarlari chatdan o‘chiriladi, menyu qoladi', function () {
    $db = App::db();
    foreach ([[1901, false], [1902, true]] as [$uid, $tgPhoto]) {
        T::$tg->reset();
        $firstUpd = T::$upd + 1;
        T::register($uid, 'uz', 'Toza', 'm', 1, ['music'], $tgPhoto);
        $calls = T::$tg->to($uid);
        $delIdx = null;
        foreach ($calls as $i => $c) {
            if ($c['method'] === 'deleteMessages') {
                $delIdx ??= $i;
            }
        }
        T::ok($delIdx !== null, "$uid: deleteMessages chaqirildi");
        $botIds = [];
        foreach (array_slice($calls, 0, (int)$delIdx) as $c) {
            if (in_array($c['method'], ['sendMessage', 'sendPhoto'], true) && isset($c['mid'])) {
                $botIds[] = $c['mid'];
            }
        }
        T::ok(count($botIds) >= 6, "$uid: bot savollari kuzatilgan (" . count($botIds) . ')');
        $userIds = [];
        foreach (range($firstUpd, T::$upd) as $u) {
            $userIds[] = $u; // msgUpdate da message_id = update_id
        }
        $deleted = [];
        foreach ($calls as $c) {
            if ($c['method'] === 'deleteMessages') {
                T::ok(count($c['params']['message_ids']) <= 100, "$uid: bir so‘rovda ≤100 ta");
                $deleted = array_merge($deleted, $c['params']['message_ids']);
            }
        }
        foreach ($botIds as $id) {
            T::ok(in_array($id, $deleted, true), "$uid: bot xabari $id o‘chirildi");
        }
        $userMsgIds = array_values(array_intersect($userIds, $deleted));
        T::eq(count($userMsgIds), $tgPhoto ? 3 : 4, "$uid: foydalanuvchi xabarlari (/start, yosh, ism" . ($tgPhoto ? '' : ', rasm') . ') o‘chirildi');
        $after = array_slice($calls, (int)$delIdx + 1);
        $done = array_values(array_filter($after, static fn($c) => $c['method'] === 'sendMessage'));
        T::eq($done[0]['params']['text'] ?? null, Lang::t('uz', 'reg.done'), "$uid: «Profilingiz tayyor» o‘chirishdan keyin keladi");
        T::ok(!in_array($done[0]['mid'] ?? -1, $deleted, true), "$uid: yakuniy xabar va menyu o‘chirilmaydi");
        T::ok(isset($done[0]['params']['reply_markup']['keyboard']), "$uid: bosh menyu klaviaturasi bor");
        T::eq((int)$db->val('SELECT COUNT(*) FROM tb_reg_msgs WHERE user_id = ?', [$uid]), 0, "$uid: kuzatuv yozuvlari tozalandi");
        foreach (T::$tg->calls as $c) {
            T::ok(!array_key_exists('_tb_reg', $c['params']), 'ichki belgi Telegramga yuborilmaydi');
        }
    }

    // Tayyor foydalanuvchining keyingi xabarlari kuzatilmaydi
    T::text(1901, '/start');
    T::text(1901, 'salom');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_reg_msgs WHERE user_id = 1901'), 0, 'ro‘yxatdan keyingi xabarlar kuzatilmaydi');

    // Navbatda kechikkan ro‘yxat xabari tugagandan keyin yetib borsa, darhol o‘chiriladi
    T::$tg->reset();
    \TB\Outbox::add(1901, 'sendMessage', ['chat_id' => 1901, 'text' => 'kech', '_tb_reg' => 1], 'late:1901');
    \TB\Outbox::process(microtime(true) + 5);
    $sent = T::$tg->last(1901, 'sendMessage');
    $del = T::$tg->last(1901, 'deleteMessage');
    T::ok($sent && $del && (int)$del['params']['message_id'] === (int)$sent['mid'], 'kechikkan xabar darhol o‘chiriladi');

    // 48 soatlik chegara va 100 talik bo‘laklar
    $uid = 1903;
    T::text($uid, '/start');
    T::cb($uid, 'lang:uz');
    $db->exec('INSERT INTO tb_reg_msgs (user_id, message_id, created_at) VALUES (?, 5, UTC_TIMESTAMP() - INTERVAL 3 DAY)', [$uid]);
    for ($i = 0; $i < 150; $i++) {
        $db->exec('INSERT IGNORE INTO tb_reg_msgs (user_id, message_id, created_at) VALUES (?, ?, UTC_TIMESTAMP())', [$uid, 100000 + $i]);
    }
    T::$tg->reset();
    T::cb($uid, 'reg:age:yes');
    T::text($uid, '25');
    T::text($uid, 'Uzun');
    T::photo($uid, 'PH_1903');
    T::cb($uid, 'reg:ph:done');
    T::cb($uid, 'reg:g:f');
    T::cb($uid, 'reg:gl:serious');
    T::cb($uid, 'reg:r:2');
    T::cb($uid, 'reg:i:art');
    T::cb($uid, 'reg:i:done');
    T::cb($uid, 'reg:ok', false);
    $dels = T::$tg->byMethod('deleteMessages');
    $all = [];
    foreach ($dels as $d) {
        T::ok(count($d['params']['message_ids']) <= 100, 'bo‘lak ≤100');
        $all = array_merge($all, $d['params']['message_ids']);
    }
    T::ok(count($dels) >= 2, '150+ xabar bir nechta deleteMessages ga bo‘linadi');
    T::ok(!in_array(5, $all, true), '48 soatdan eski xabar so‘ralmaydi');
    T::ok(in_array(100149, $all, true), 'yangi xabarlar so‘raladi');
    T::eq(T::user($uid)['reg_step'], 'done', 'ro‘yxat tugadi');
});
