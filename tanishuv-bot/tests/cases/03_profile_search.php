<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Lang;
use TB\Users;

$t('profile: har maydonni alohida tahrirlash boshqa maydonlarni o‘zgartirmaydi', function () {
    $uid = 2001;
    T::register($uid, 'uz', 'Asl Ism', 'm', 3, ['music', 'sport']);
    $snap = static function () use ($uid): array {
        $u = T::user($uid);
        return ['name' => $u['name'], 'photos' => $u['photos'], 'gender' => $u['gender'], 'region' => (int)$u['region'], 'interests' => $u['interests']];
    };
    $before = $snap();

    T::cb($uid, 'pr:set');
    T::cb($uid, 'pr:e:name');
    T::text($uid, 'Yangi Ism');
    $after = $snap();
    T::eq($after['name'], 'Yangi Ism', 'ism o‘zgardi');
    T::eq([$after['photos'], $after['gender'], $after['region'], $after['interests']], [$before['photos'], $before['gender'], $before['region'], $before['interests']], 'ism tahriri boshqa maydonlarga tegmadi');

    $before = $snap();
    T::cb($uid, 'pr:e:gender');
    T::cb($uid, 'e:g:f');
    $after = $snap();
    T::eq($after['gender'], 'f', 'jins o‘zgardi');
    T::eq([$after['name'], $after['photos'], $after['region'], $after['interests']], [$before['name'], $before['photos'], $before['region'], $before['interests']], 'jins tahriri boshqa maydonlarga tegmadi');

    $before = $snap();
    T::cb($uid, 'pr:e:region');
    T::cb($uid, 'e:r:13');
    $after = $snap();
    T::eq($after['region'], 13, 'hudud o‘zgardi');
    T::eq([$after['name'], $after['photos'], $after['gender'], $after['interests']], [$before['name'], $before['photos'], $before['gender'], $before['interests']], 'hudud tahriri boshqa maydonlarga tegmadi');

    $before = $snap();
    T::cb($uid, 'pr:e:int');
    T::cb($uid, 'e:i:sport');
    T::cb($uid, 'e:i:art');
    T::eq(T::user($uid)['interests'], $before['interests'], 'qiziqishlar saqlashgacha o‘zgarmaydi');
    T::cb($uid, 'e:i:save');
    $after = $snap();
    T::eq(explode(',', (string)$after['interests']), ['music', 'art'], 'qiziqishlar saqlandi');
    T::eq([$after['name'], $after['photos'], $after['gender'], $after['region']], [$before['name'], $before['photos'], $before['gender'], $before['region']], 'qiziqish tahriri boshqa maydonlarga tegmadi');

    $before = $snap();
    T::cb($uid, 'pr:e:photo');
    T::photo($uid, 'NEW1');
    T::photo($uid, 'NEW2');
    T::cb($uid, 'e:ph:save');
    $after = $snap();
    T::eq(json_decode((string)$after['photos'], true), ['NEW1', 'NEW2'], 'rasmlar qoralamadan saqlandi');
    T::eq([$after['name'], $after['gender'], $after['region'], $after['interests']], [$before['name'], $before['gender'], $before['region'], $before['interests']], 'rasm tahriri boshqa maydonlarga tegmadi');

    // stale edit callback (holat yo‘q) ishlamaydi
    T::cb($uid, 'e:g:m');
    T::eq(T::user($uid)['gender'], 'f', 'holatsiz e:g:m rad etildi');
});

$t('profile: bekor qilingan foto qoralamasi eski rasmlarni o‘chirmaydi', function () {
    $uid = 2002;
    T::register($uid, 'ru', 'Olga', 'f', 1);
    $orig = T::user($uid)['photos'];
    T::cb($uid, 'pr:e:photo');
    T::photo($uid, 'DRAFT1');
    T::photo($uid, 'DRAFT2');
    T::eq(T::user($uid)['photos'], $orig, 'qoralama paytida eski rasmlar joyida');
    T::cb($uid, 'e:x');
    T::eq(T::user($uid)['photos'], $orig, 'bekor qilingandan keyin eski rasmlar joyida');
    T::eq(T::user($uid)['state'], null, 'holat tozalandi');
    T::cb($uid, 'e:ph:save');
    T::eq(T::user($uid)['photos'], $orig, 'bekor qilingandan keyingi Saqlash ishlamaydi');
    // qoralamada 5 ta chegarasi
    T::cb($uid, 'pr:e:photo');
    for ($i = 0; $i < 7; $i++) {
        T::photo($uid, 'D' . $i);
    }
    T::cb($uid, 'e:ph:save');
    T::eq(count(Users::photos(T::user($uid))), 5, 'tahrirda ham 5 ta chegarasi');
});

$t('profile: review bosqichidan tahrirlash', function () {
    $uid = 2003;
    T::text($uid, '/start');
    T::cb($uid, 'lang:en');
    T::cb($uid, 'reg:age:yes');
    T::text($uid, '25');
    T::text($uid, 'Kate');
    T::photo($uid, 'K1');
    T::cb($uid, 'reg:ph:done');
    T::cb($uid, 'reg:g:f');
    T::cb($uid, 'reg:gl:serious');
    T::cb($uid, 'reg:r:2');
    T::cb($uid, 'reg:i:art');
    T::cb($uid, 'reg:i:done');
    T::cb($uid, 'reg:edit');
    T::cb($uid, 'pr:e:name');
    T::text($uid, 'Katherine');
    T::eq(T::user($uid)['name'], 'Katherine', 'review dan ism tahrirlandi');
    T::eq(T::user($uid)['reg_step'], 'review', 'hali review bosqichida');
    T::cb($uid, 'pr:my');
    T::eq(T::user($uid)['reg_step'], 'review', 'review da pr:my ruxsat etilmaydi');
    T::cb($uid, 'reg:ok');
    T::eq(T::user($uid)['reg_step'], 'done', 'tasdiqlandi');
});

/** Qidiruv uchun bir nechta tayyor profil yaratish (to‘g‘ridan-to‘g‘ri DB ga). */
function mkUser(int $id, string $g, int $region, string $status = 'active', string $step = 'done', int $age = 1): void
{
    App::db()->exec(
        "INSERT INTO tb_users (id, lang, reg_step, age_confirmed, name, photos, gender, region, interests, status, created_at, updated_at, last_seen_at)
         VALUES (?, 'uz', ?, ?, ?, ?, ?, ?, 'music', ?, UTC_TIMESTAMP(), UTC_TIMESTAMP(), UTC_TIMESTAMP() - INTERVAL ? SECOND)",
        [$id, $step, $age, 'U' . $id, json_encode(['PH' . $id]), $g, $region, $status, $id % 1000]
    );
}

function boost(int $uid, string $aud, int $hours = 24): void
{
    App::db()->exec(
        'INSERT INTO tb_boosts (user_id, audience, order_id, starts_at, expires_at) VALUES (?, ?, ?, UTC_TIMESTAMP() - INTERVAL 1 MINUTE, UTC_TIMESTAMP() + INTERVAL ? HOUR)',
        [$uid, $aud, bin2hex(random_bytes(16)), $hours]
    );
}

/** Ketma-ket ko‘rsatilgan anketalar ID lari. */
function browse(int $viewer, string $mode, int $max = 20): array
{
    $seen = [];
    T::cb($viewer, 's:' . $mode);
    for ($i = 0; $i < $max; $i++) {
        $u = T::user($viewer);
        if (empty($u['card_target'])) {
            break;
        }
        $seen[] = (int)$u['card_target'];
        T::cb($viewer, 'r:n:' . $u['card_nonce'], false);
    }
    return $seen;
}

$t('search: jins filtri, hudud va boost ustuvorligi, boost filtrni chetlab o‘tmaydi', function () {
    T::isolate();
    $viewer = 3000; // ayol, 1-hudud
    T::register($viewer, 'uz', 'Viewer', 'f', 1);
    mkUser(3101, 'm', 1);          // erkak, bir xil hudud
    mkUser(3102, 'm', 7);          // erkak, boshqa hudud, ayollar uchun boost
    mkUser(3103, 'm', 7);          // erkak, boshqa hudud, erkaklar uchun boost (ayol viewer uchun ustuvor emas)
    mkUser(3104, 'm', 9);          // erkak, boshqa hudud
    mkUser(3201, 'f', 1);          // ayol, ayollar uchun boost — erkak qidiruvida chiqmasligi kerak
    boost(3102, 'f');
    boost(3103, 'm');
    boost(3201, 'f');
    $list = browse($viewer, 'm');
    T::eq($list[0] ?? null, 3102, 'faol boost (mos auditoriya) birinchi');
    T::eq($list[1] ?? null, 3101, 'keyin bir xil hudud');
    T::eq(array_values(array_diff($list, [3101, 3102, 3103, 3104])), [], 'erkak qidiruvida faqat erkaklar (boostli ayol chiqmadi)');
    T::ok(!in_array(3201, $list, true), 'boost jins filtrini chetlab o‘tmadi');
    T::ok(!in_array($viewer, $list, true), 'o‘zi chiqmadi');

    $viewer2 = 3001;
    T::register($viewer2, 'uz', 'Viewer2', 'm', 9);
    $f = browse($viewer2, 'f');
    foreach ($f as $id) {
        T::eq(T::user($id)['gender'], 'f', "qizlar qidiruvida faqat ayollar ($id)");
    }
});

$t('search: o‘zi, suspended, tugallanmagan va 18+ tasdiqlamaganlar chiqmaydi; 24 soat qoidasi', function () {
    T::isolate();
    $viewer = 3300;
    T::register($viewer, 'en', 'Me', 'm', 2);
    mkUser(3301, 'f', 2);
    mkUser(3302, 'f', 2, 'suspended');
    mkUser(3303, 'f', 2, 'active', 'review');
    mkUser(3304, 'f', 2, 'active', 'done', 0);
    $list = browse($viewer, 'a', 50);
    T::ok(in_array(3301, $list, true), 'oddiy faol profil ko‘rindi');
    T::ok(!in_array($viewer, $list, true), 'o‘zi chiqmadi');
    T::ok(!in_array(3302, $list, true), 'suspended chiqmadi');
    T::ok(!in_array(3303, $list, true), 'tugallanmagan chiqmadi');
    T::ok(!in_array(3304, $list, true), '18+ tasdiqlamagan chiqmadi');
    $again = browse($viewer, 'a', 50);
    T::ok(!in_array(3301, $again, true), '24 soat ichida qayta chiqmadi');
    App::db()->exec('UPDATE tb_seen SET seen_at = UTC_TIMESTAMP() - INTERVAL 25 HOUR WHERE viewer_id = ?', [$viewer]);
    $later = browse($viewer, 'a', 50);
    T::ok(in_array(3301, $later, true), '24 soatdan keyin yana chiqdi');
});

$t('search: soxta nishon, eskirgan nonce, takroriy reaksiya, mutual like va match', function () {
    T::isolate();
    $a = 3400;
    $b = 3401;
    $c = 3402;
    T::register($a, 'uz', 'Aziz', 'm', 1);
    T::register($b, 'ru', 'Bella', 'f', 1);
    T::register($c, 'en', 'Cara', 'f', 1);
    $db = App::db();

    T::cb($a, 's:f');
    $ua = T::user($a);
    $t1 = (int)$ua['card_target'];
    $n1 = (string)$ua['card_nonce'];
    T::ok(in_array($t1, [$b, $c], true), 'A ga ayol ko‘rsatildi');

    // Soxta: boshqa foydalanuvchining nonce i yoki tasodifiy nonce
    T::cb($b, 's:m');
    $nb = (string)T::user($b)['card_nonce'];
    T::cb($a, 'r:l:' . $nb, false);
    T::cb($a, 'r:l:' . bin2hex(random_bytes(6)), false);
    T::cb($a, 'r:l:' . $n1 . 'x', false);
    T::cb($a, 'r:l:3401', false);
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_reactions WHERE from_id = ?', [$a]), 0, 'soxta callbacklar reaksiya yaratmadi');

    // Eskirgan nonce: Keyingisi bosilgach eski nonce ishlamaydi
    T::cb($a, 'r:n:' . $n1, false);
    $n2 = (string)T::user($a)['card_nonce'];
    T::ok($n2 !== $n1, 'nonce yangilandi');
    T::cb($a, 'r:l:' . $n1, false);
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_reactions WHERE from_id = ?', [$a]), 0, 'eskirgan nonce ishlamadi');

    // B, A ni yoqtiradi (B ning qidiruvi erkak)
    T::eq((int)T::user($b)['card_target'], $a, 'B ga A ko‘rsatildi');
    T::cb($b, 'r:l:' . $nb, false);
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_reactions WHERE from_id = ? AND to_id = ? AND kind = 'like'", [$b, $a]), 1, 'B→A like');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_matches'), 0, 'hali match yo‘q');

    // A "Menga qiziqqanlar" → Yoqdi bosganlar → B → super like => match
    T::$tg->reset();
    T::cb($a, 'lk:l');
    T::eq((int)T::user($a)['card_target'], $b, 'A ro‘yxatida B');
    T::cb($a, 'r:s:' . T::user($a)['card_nonce'], false);
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_matches WHERE user_a = ? AND user_b = ?', [$a, $b]), 1, 'bitta match yaratildi');
    $mid = (int)$db->val('SELECT id FROM tb_matches WHERE user_a = ? AND user_b = ?', [$a, $b]);
    T::eq(T::data($a, 'c:s:'), 'c:s:' . $mid, 'A ga "Suhbat boshlash" tugmasi');
    T::eq(T::data($b, 'c:s:'), 'c:s:' . $mid, 'B ga "Suhbat boshlash" tugmasi');
    T::ok(str_contains(implode("\n", T::texts($b)), 'Aziz'), 'B ga match xabari (rus tilida)');
    T::ok(in_array(Lang::t('ru', 'match.start'), array_column(array_merge(...array_map(fn($c) => $c['params']['reply_markup']['inline_keyboard'][0] ?? [], T::$tg->to($b))), 'text'), true), 'B tugmasi o‘z tilida');

    // Takroriy reaksiya: A yana ro‘yxatga kiradi, B ga yana like bosadi
    $likesBefore = (int)$db->val('SELECT supers + likes FROM tb_daily_limits WHERE user_id = ? AND day = UTC_DATE()', [$a]);
    T::cb($a, 'lk:l');
    T::eq((int)T::user($a)['card_target'], $b, 'B yana ko‘rindi');
    T::cb($a, 'r:l:' . T::user($a)['card_nonce'], false);
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_reactions WHERE from_id = ? AND to_id = ? AND kind IN ('like','super')", [$a, $b]), 1, 'takroriy reaksiya yozilmadi');
    T::eq((int)$db->val('SELECT supers + likes FROM tb_daily_limits WHERE user_id = ? AND day = UTC_DATE()', [$a]), $likesBefore, 'takroriy reaksiya limitni kamaytirmadi');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_matches'), 1, 'ikkinchi match yaratilmadi');

    // Saqlash va "Profilimni saqlaganlar"
    T::cb($c, 's:m');
    T::eq((int)T::user($c)['card_target'], $a, 'C ga A');
    T::cb($c, 'r:b:' . T::user($c)['card_nonce'], false);
    T::cb($c, 'r:b:' . T::user($c)['card_nonce'], false);
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_reactions WHERE from_id = ? AND kind = 'save'", [$c]), 1, 'saqlash bir marta');
    T::cb($a, 'lk:b');
    T::eq((int)T::user($a)['card_target'], $c, '"Profilimni saqlaganlar" da C');
    T::cb($c, 'pr:sv');
    T::eq((int)T::user($c)['card_target'], $a, '"Saqlaganlarim" da A');
});

$t('search: kunlik limitlar (bepul 1 super like) va UTC yozuvi', function () {
    T::isolate();
    $a = 3500;
    T::register($a, 'uz', 'Limit', 'm', 1);
    mkUser(3501, 'f', 1);
    mkUser(3502, 'f', 1);
    T::cb($a, 's:f');
    T::cb($a, 'r:s:' . T::user($a)['card_nonce'], false);
    $t2 = (int)T::user($a)['card_target'];
    T::cb($a, 'r:s:' . T::user($a)['card_nonce'], false);
    T::eq((int)App::db()->val("SELECT COUNT(*) FROM tb_reactions WHERE from_id = ? AND kind = 'super'", [$a]), 1, 'bepul: kuniga 1 super like');
    T::ok(str_contains(T::lastText($a), 'UTC'), 'limit xabarida UTC aniq yozilgan');
    T::eq((int)T::user($a)['card_target'], $t2, 'limitda karta o‘zgarmadi');
});
