<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Blocks;
use TB\Cron;
use TB\Lang;
use TB\Retention;
use TB\Search;
use TB\Settings;
use TB\Users;

$t('growth: bloklash qidiruv, ro‘yxat, like va suhbatdan chiqaradi (ikki tomonlama)', function () {
    T::isolate();
    $a = 8100;
    $b = 8101;
    $c = 8102;
    T::register($a, 'uz', 'Aziz', 'm', 1);
    T::register($b, 'uz', 'Bella', 'f', 1);
    T::register($c, 'uz', 'Cara', 'f', 1);
    $db = App::db();

    T::cb($a, 's:f');
    $ua = T::user($a);
    T::ok(T::data($a, 'r:x:') !== null, 'kartada Bloklash tugmasi bor');
    $target = (int)$ua['card_target'];
    T::cb($a, 'r:x:' . $ua['card_nonce']);
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_blocks WHERE blocker_id = ? AND blocked_id = ?', [$a, $target]), 1, 'blok yozildi');
    $next = (int)T::user($a)["card_target"];
    T::ok($next !== $target && in_array($next, [$b, $c], true), 'keyingi karta boshqa odam');
    // ikki tomonlama: bloklangan ham A ni ko‘rmaydi
    T::eq(Search::candidate(array_merge(T::user($target), ["search_pref" => "m"])), null, 'bloklangan odam A ni ko‘rmaydi');
    T::eq(Blocks::between($a, $target), true, 'between() ikki tomonlama');

    // bloklangan odamga like berib bo‘lmaydi (eskirgan karta bilan ham)
    $db->exec("INSERT IGNORE INTO tb_reactions (from_id, to_id, kind, created_at) VALUES (?, ?, 'like', UTC_TIMESTAMP())", [$target, $a]);
    T::cb($a, 'lk:l');
    T::eq((int)T::user($a)['card_target'] === $target, false, 'bloklangan odam «yoqdi» ro‘yxatida ko‘rinmaydi');

    // suhbat paytida bloklash suhbatni tugatadi
    $db->exec('INSERT IGNORE INTO tb_matches (user_a, user_b, created_at) VALUES (?, ?, UTC_TIMESTAMP())', [min($a, $next), max($a, $next)]);
    $mid = (int)$db->val('SELECT id FROM tb_matches WHERE user_a = ? AND user_b = ?', [min($a, $next), max($a, $next)]);
    T::cb($a, 'c:s:' . $mid);
    $cid = (int)T::user($a)['active_chat_id'];
    T::ok($cid > 0, 'suhbat boshlandi');
    T::eq(T::data($a, 'c:b:'), 'c:b:' . $cid, 'suhbatda Bloklash tugmasi');
    T::cb($a, 'c:b:' . $cid);
    T::eq(T::user($a)['active_chat_id'], null, 'suhbat tugadi');
    T::eq(T::user($next)['active_chat_id'], null, 'suhbatdosh ham chiqdi');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_blocks WHERE blocker_id = ? AND blocked_id = ?', [$a, $next]), 1, 'suhbatdosh bloklandi');
    // bloklangandan keyin suhbat boshlab bo‘lmaydi
    T::cb($next, 'c:s:' . $mid);
    T::eq(T::user($next)['active_chat_id'], null, 'bloklangan match bo‘yicha suhbat ochilmadi');

    // /blocks va tozalash
    T::text($a, '/blocks');
    T::ok(str_contains(T::lastText($a), '2'), '/blocks soni ko‘rsatildi');
    T::cb($a, 'bk:clear');
    T::eq(Blocks::count($a), 0, 'bloklar tozalandi');

    // /delete bloklarni o‘chiradi
    Blocks::add(new \TB\Ctx($b, 1, null, null), $c);
    T::cb($b, 'del:yes');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_blocks WHERE blocker_id = ? OR blocked_id = ?', [$b, $b]), 0, '/delete bloklarni o‘chirdi');
});

$t('growth: «kim yoqtirdi» faqat Premium (likes_gate), Premium bilan ochiladi', function () {
    T::isolate();
    $me = 8200;
    $her = 8201;
    T::register($me, 'uz', 'Aziz', 'm', 1);
    T::register($her, 'uz', 'Bella', 'f', 1);
    Settings::set('likes_gate', '1');
    App::db()->exec("INSERT INTO tb_reactions (from_id, to_id, kind, created_at) VALUES (?, ?, 'like', UTC_TIMESTAMP())", [$her, $me]);

    T::$tg->reset();
    T::cb($me, 'lk:l');
    T::eq(T::lastText($me), Lang::t('uz', 'likes.locked', ['n' => 1]), 'bepul foydalanuvchiga qulf matni va soni');
    T::eq(T::user($me)['card_ctx'] === 'll', false, 'ro‘yxat ochilmadi');
    T::eq(T::data($me, 'pm:menu'), 'pm:menu', 'Premium tugmasi');
    T::cb($me, 'pm:menu');
    T::ok(str_contains(T::lastText($me), Lang::t('uz', 'premium.title')), 'pm:menu Premium menyusini ochdi');

    App::db()->exec("UPDATE tb_users SET premium_until = UTC_TIMESTAMP() + INTERVAL 1 DAY WHERE id = ?", [$me]);
    T::cb($me, 'lk:l');
    T::eq((int)T::user($me)['card_target'], $her, 'Premium foydalanuvchi ro‘yxatni ko‘radi');

    // «Juda yoqdi» va saqlanganlar qulfsiz
    Settings::set('likes_gate', '0');
});

$t('growth: referal: /start ref_ yoziladi, tugatgach mukofot bir marta, o‘z-o‘ziga va chegara', function () {
    T::isolate();
    $inv = 8300;
    $f1 = 8301;
    $f2 = 8302;
    T::register($inv, 'uz', 'Aziz', 'm', 1);
    $db = App::db();

    T::text($inv, '/invite');
    T::ok(str_contains(T::lastText($inv), 'ref_' . $inv) || str_contains(T::lastText($inv), Lang::t('uz', 'invite.nolink')), '/invite havola yoki xabar beradi');

    // o‘z-o‘ziga taklif yozilmaydi
    T::text(8399, '/start ref_8399');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_referrals WHERE invited_id = 8399'), 0, 'o‘z-o‘ziga referal yozilmadi');

    T::text($f1, '/start ref_' . $inv);
    T::eq((int)$db->val('SELECT inviter_id FROM tb_referrals WHERE invited_id = ?', [$f1]), $inv, 'referal yozildi');
    T::eq(T::user($inv)['premium_until'], null, 'ro‘yxatdan o‘tmasdan mukofot yo‘q');
    T::cb($f1, 'lang:uz');
    T::cb($f1, 'reg:age:yes');
    T::text($f1, '24');
    T::text($f1, 'Bella');
    T::photo($f1, 'PH_' . $f1);
    T::cb($f1, 'reg:ph:done');
    T::cb($f1, 'reg:g:f');
    T::cb($f1, 'reg:gl:serious');
    T::cb($f1, 'reg:r:1');
    T::cb($f1, 'reg:i:music');
    T::cb($f1, 'reg:i:done');
    T::$tg->reset();
    T::cb($f1, 'reg:ok', false);
    $pu = T::user($inv)['premium_until'];
    T::ok($pu !== null && strtotime($pu . ' UTC') > time() + 3600 * 23, 'taklif qilgan 1 kun Premium oldi');
    T::ok(str_contains(T::lastText($inv), Lang::t('uz', 'invite.reward', ['days' => 1])), 'taklif qilganga xabar');
    T::ok(App::db()->val('SELECT rewarded_at FROM tb_referrals WHERE invited_id = ?', [$f1]) !== null, 'mukofot belgilandi');

    // mavjud foydalanuvchi keyin /start ref_ bilan kirsa yozilmaydi
    T::text($inv, '/start ref_' . $f1);
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_referrals WHERE invited_id = ?', [$inv]), 0, 'ro‘yxatdan o‘tgan foydalanuvchiga referal yozilmaydi');

    // chegara
    Settings::set('ref_max_rewards', '1');
    T::text($f2, '/start ref_' . $inv);
    T::register($f2, 'uz', 'Cara', 'f', 1);
    $pu2 = T::user($inv)['premium_until'];
    T::eq($pu2, $pu, 'chegaradan keyin mukofot qo‘shilmadi');
    Settings::set('ref_max_rewards', '30');
});

$t('growth: eslatmalar: yangi like, 24 soatda 1 marta, faolsizlik, o‘chirish, bloklaganlarga yo‘q', function () {
    T::isolate();
    $me = 8400;
    $her = 8401;
    T::register($me, 'ru', 'Aziz', 'm', 1);
    T::register($her, 'uz', 'Bella', 'f', 1);
    $db = App::db();
    $db->exec("UPDATE tb_users SET last_seen_at = UTC_TIMESTAMP() - INTERVAL 8 HOUR WHERE id = ?", [$me]);
    $db->exec("INSERT INTO tb_reactions (from_id, to_id, kind, created_at) VALUES (?, ?, 'like', UTC_TIMESTAMP() - INTERVAL 1 HOUR)", [$her, $me]);

    Settings::set('retention', '0');
    T::eq(Retention::run(), 0, 'o‘chiq bo‘lsa eslatma yo‘q');
    Settings::set('retention', '1');
    T::$tg->reset();
    $n = Retention::run();
    \TB\Outbox::process(microtime(true) + 5);
    T::ok($n >= 1, 'eslatma navbatga tushdi');
    T::eq(T::lastText($me), Lang::t('ru', 'retention.likes', ['n' => 1]), 'like eslatmasi o‘z tilida');
    T::eq(Retention::run(), 0, '24 soat ichida takror yuborilmadi');

    // bot bloklangan foydalanuvchiga yuborilmaydi
    $db->exec("DELETE FROM tb_notices WHERE user_id = ?", [$me]);
    $db->exec("UPDATE tb_users SET blocked_bot = 1 WHERE id = ?", [$me]);
    T::eq(Retention::run(), 0, 'botni bloklaganga yuborilmadi');
    $db->exec("UPDATE tb_users SET blocked_bot = 0 WHERE id = ?", [$me]);

    // like dan keyin kirgan bo‘lsa eslatma kerak emas
    $db->exec("UPDATE tb_users SET last_seen_at = UTC_TIMESTAMP() WHERE id = ?", [$me]);
    T::eq(Retention::run(), 0, 'yaqinda kirgan foydalanuvchiga yuborilmadi');

    // faolsizlik: 5 kun
    $db->exec("UPDATE tb_users SET last_seen_at = UTC_TIMESTAMP() - INTERVAL 5 DAY WHERE id = ?", [$me]);
    $db->exec("DELETE FROM tb_notices WHERE user_id = ?", [$me]);
    T::$tg->reset();
    Retention::run();
    \TB\Outbox::process(microtime(true) + 5);
    $texts = T::texts($me);
    T::ok(in_array(Lang::t('ru', 'retention.inactive'), $texts, true), 'faolsizlik eslatmasi');
    // 40 kun faol emas — yuborilmaydi
    $db->exec("UPDATE tb_users SET last_seen_at = UTC_TIMESTAMP() - INTERVAL 40 DAY WHERE id = ?", [$me]);
    $db->exec("DELETE FROM tb_notices WHERE user_id = ?", [$me]);
    T::eq(Retention::run(), 0, '30 kundan eski faolsizlarga yuborilmadi');

    // CRON statistikasida ko‘rinadi
    $r = Cron::run(microtime(true) + 20);
    T::ok(array_key_exists('retention', $r), 'cron natijasida retention');
});

$t('growth: yangi anketalar tekshiruvi: navbat, tasdiqlash, yashirish', function () {
    T::isolate();
    $admin = 9000001;
    $u = 8500;
    T::register($admin, 'uz', 'Admin', 'm', 1);
    $db = App::db();
    Settings::set('photo_review', '1');
    T::$tg->reset();
    T::register($u, 'uz', 'Dilya', 'f', 1);
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_profile_reviews WHERE user_id = ? AND status = 'pending'", [$u]), 1, 'navbatga tushdi');
    T::ok(in_array(Lang::t('uz', 'admin.review_new'), T::texts($admin), true), 'adminga xabar');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_profile_reviews WHERE user_id = ?", [$admin]), 0, 'adminning o‘zi navbatga tushmaydi');

    T::cb($admin, 'a:pq');
    $rid = (int)$db->val("SELECT id FROM tb_profile_reviews WHERE user_id = ?", [$u]);
    T::eq(T::data($admin, 'a:pa:'), 'a:pa:' . $rid, 'Yaxshi tugmasi');
    T::cb($admin, 'a:ph:' . $rid);
    T::eq((int)$db->val('SELECT mod_hidden FROM tb_user_ext WHERE user_id = ?', [$u]), 1, 'yashirildi');
    T::eq($db->val('SELECT status FROM tb_profile_reviews WHERE id = ?', [$rid]), 'hidden', 'holat hidden');
    T::cb($admin, 'a:ph:' . $rid);   // takror bosish zarar bermaydi
    T::eq($db->val('SELECT status FROM tb_profile_reviews WHERE id = ?', [$rid]), 'hidden', 'takroriy qaror o‘zgartirmadi');

    // oddiy foydalanuvchi admin callbackini bosa olmaydi
    T::cb($u, 'a:pa:' . $rid);
    T::eq($db->val('SELECT status FROM tb_profile_reviews WHERE id = ?', [$rid]), 'hidden', 'admin bo‘lmagan qaror qila olmadi');

    // o‘chiq bo‘lsa navbat to‘lmaydi
    Settings::set('photo_review', '0');
    T::register(8501, 'uz', 'Zara', 'f', 1);
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_profile_reviews WHERE user_id = 8501"), 0, 'o‘chiq bo‘lsa navbatga tushmaydi');
});

$t('growth: qidiruv tartibi: umumiy qiziqishlar va yaqin yosh; statistika voronkasi', function () {
    T::isolate();
    $me = 8600;
    $x = 8601;
    $y = 8602;
    T::register($me, 'uz', 'Aziz', 'm', 1, ['music', 'sport'], false, 25);
    T::register($x, 'uz', 'Xadicha', 'f', 1, ['books'], false, 25);
    T::register($y, 'uz', 'Yulduz', 'f', 1, ['music', 'sport'], false, 40);
    // x oxirgi faol (last_seen_at bo‘yicha oldinda bo‘lardi), lekin y bilan 2 ta umumiy qiziqish
    App::db()->exec('UPDATE tb_users SET last_seen_at = UTC_TIMESTAMP() WHERE id = ?', [$x]);
    App::db()->exec('UPDATE tb_users SET last_seen_at = UTC_TIMESTAMP() - INTERVAL 1 HOUR WHERE id = ?', [$y]);
    T::eq(Search::candidate(Users::find($me)), $y, 'umumiy qiziqishlari ko‘p bo‘lgan odam birinchi');

    $d = \TB\Admin::statsData();
    foreach (['blocks', 'refs', 'refpaid', 'xtr7', 'xtr30', 'rt24', 'rvpending', 'funnel'] as $k) {
        T::ok(array_key_exists($k, $d), 'statistikada ' . $k);
    }
    T::ok(str_contains($d['funnel'], 'done:'), 'voronka bosqichlari');
});
