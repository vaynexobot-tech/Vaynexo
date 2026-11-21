<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Lang;
use TB\Settings;
use TB\Users;

/** Karta ochadi: searcher qidiruvni boshlaydi, ko‘rsatilgan nishon ID sini qaytaradi. */
function openCard(int $uid, string $pref = 'f'): ?int
{
    T::cb($uid, 's:' . $pref);
    $u = Users::find($uid);
    return $u['card_target'] !== null ? (int)$u['card_target'] : null;
}

$t('yosh: ro‘yxatda so‘raladi, 18 dan kichik va admin chegarasi tekshiriladi, kartada ko‘rinadi', function () {
    $uid = 9101;
    T::text($uid, '/start');
    T::cb($uid, 'lang:uz');
    T::cb($uid, 'reg:age:yes');
    T::eq(T::user($uid)['reg_step'], 'agenum', '18+ dan keyin yosh so‘raladi');
    T::text($uid, 'yigirma');
    T::eq(T::lastText($uid), Lang::t('uz', 'err.age', ['min' => 18, 'max' => 99]), 'raqam bo‘lmasa xato');
    T::text($uid, '16');
    $u = T::user($uid);
    T::eq($u['reg_step'], 'age', '18 dan kichik yosh: 18+ bosqichiga qaytadi');
    T::eq((int)$u['age_confirmed'], 0, '18+ tasdig‘i bekor qilindi');
    Settings::set('age_min', '21');
    Settings::set('age_max', '45');
    T::cb($uid, 'reg:age:yes');
    T::text($uid, '19');
    T::eq(T::lastText($uid), Lang::t('uz', 'err.age', ['min' => 21, 'max' => 45]), 'admin chegarasidan past yosh rad etildi');
    T::text($uid, '50');
    T::eq(T::user($uid)['reg_step'], 'agenum', 'chegaradan yuqori yosh rad etildi');
    T::text($uid, '30');
    T::eq(Users::age(Users::find($uid)), 30, 'yosh saqlandi');
    Settings::set('age_min', '18');
    Settings::set('age_max', '99');
    T::register(9102, 'ru', 'Анна', 'f', 2, ['music'], false, 27, 'friends');
    $u = Users::find(9102);
    T::eq($u['goal'], 'friends', 'maqsad saqlandi');
    $card = \TB\Profile::cardText('ru', $u);
    T::ok(str_contains($card, 'Анна, 27'), 'kartada ism va yosh');
    T::ok(str_contains($card, Lang::t('ru', 'goal.friends')), 'kartada maqsad');
});

$t('yangilanish: eski profilda yosh yoki maqsad bo‘lmasa, o‘sha bosqich so‘raladi', function () {
    $uid = 9103;
    T::register($uid, 'uz', 'Eski', 'm', 1);
    App::db()->exec('DELETE FROM tb_user_ext WHERE user_id = ?', [$uid]);
    T::$tg->reset();
    T::text($uid, '/start');
    T::eq(T::user($uid)['reg_step'], 'agenum', 'yoshsiz profil agenum ga qaytdi');
    T::text($uid, '33');
    T::eq(T::user($uid)['reg_step'], 'name', 'keyingi bosqich');
    T::cb($uid, 'reg:ok', false);
    T::ok(T::user($uid)['reg_step'] !== 'done', 'maqsadsiz tasdiqlab bo‘lmaydi');
    // ism, rasm, jins bor: firstMissing goal ga olib boradi
    App::db()->exec("UPDATE tb_users SET reg_step = 'review' WHERE id = ?", [$uid]);
    T::cb($uid, 'reg:ok', false);
    T::eq(T::user($uid)['reg_step'], 'goal', 'maqsad bosqichi so‘raldi');
    T::cb($uid, 'reg:gl:chat');
    T::cb($uid, 'reg:r:1');
    T::cb($uid, 'reg:i:done');
    T::cb($uid, 'reg:ok', false);
    T::eq(T::user($uid)['reg_step'], 'done', 'profil yana to‘liq');
});

$t('qidiruv: yosh oralig‘i, maqsad, faqat tasdiqlanganlar va yashirilganlar filtri', function () {
    T::isolate();
    $me = 9110;
    T::register($me, 'uz', 'Qidiruvchi', 'm', 1, ['music'], false, 30);
    T::register(9111, 'uz', 'Yosh', 'f', 1, ['music'], false, 20, 'chat');
    T::register(9112, 'uz', 'Orta', 'f', 1, ['music'], false, 30, 'serious');
    T::register(9113, 'uz', 'Katta', 'f', 1, ['music'], false, 40, 'friends');
    T::cb($me, 's:ag:2');
    T::eq((int)Users::find($me)['pref_age_min'], 25, 'yosh filtri saqlandi');
    T::eq(openCard($me), 9112, '25–34 filtri faqat 30 yoshlini ko‘rsatadi');
    App::db()->exec('DELETE FROM tb_seen WHERE viewer_id = ?', [$me]);
    T::cb($me, 's:ag:0');
    T::cb($me, 's:gl:friends');
    T::eq(openCard($me), 9113, 'maqsad filtri');
    App::db()->exec('DELETE FROM tb_seen WHERE viewer_id = ?', [$me]);
    T::cb($me, 's:gl:any');
    T::cb($me, 's:ver');
    T::eq((int)Users::find($me)['pref_verified'], 1, 'faqat tasdiqlanganlar yoqildi');
    T::eq(openCard($me), null, 'tasdiqlangan yo‘q — bo‘sh');
    Users::updateExt(9111, ['verified' => 1]);
    T::eq(openCard($me), 9111, 'tasdiqlangan ko‘rsatildi');
    T::cb($me, 's:ver');
    App::db()->exec('DELETE FROM tb_seen WHERE viewer_id = ?', [$me]);
    Users::updateExt(9111, ['mod_hidden' => 1]);
    Users::updateExt(9112, ['mod_hidden' => 1]);
    T::eq(openCard($me), 9113, 'yashirilganlar qidiruvda chiqmaydi');
    T::ok(!Users::isVisible(Users::find(9111)), 'yashirilgan anketa ko‘rinmas');
    Users::updateExt(9111, ['mod_hidden' => 0]);
    Users::updateExt(9112, ['mod_hidden' => 0]);
});

$t('like bilan xabar: yetkazish, havola va so‘z filtri, moderatsiya, o‘chiq rejim', function () {
    T::isolate();
    $db = App::db();
    $me = 9120;
    $her = 9121;
    T::register($me, 'uz', 'Bek', 'm', 1);
    T::register($her, 'ru', 'Лола', 'f', 1);
    Settings::set('likemsg_mode', 'on');
    T::eq(openCard($me), $her, 'karta ochildi');
    $cb = T::data($me, 'r:m:');
    T::ok($cb !== null, 'kartada «Xabar bilan like» tugmasi');
    T::cb($me, $cb);
    T::eq(T::user($me)['state'], 'likemsg', 'xabar kutilmoqda');
    T::text($me, 'Yoz menga @lola_insta');
    T::eq(T::lastText($me), Lang::t('uz', 'likemsg.no_links'), '@username bloklandi');
    T::text($me, 'https://example.com');
    T::eq(T::lastText($me), Lang::t('uz', 'likemsg.no_links'), 'havola bloklandi');
    Settings::set('likemsg_stopwords', 'pul, karta');
    T::text($me, 'Menga KARTA raqamingni ber');
    T::eq(T::lastText($me), Lang::t('uz', 'likemsg.blocked'), 'taqiqlangan so‘z');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_like_msgs WHERE from_id = ? AND status = 'blocked'", [$me]), 1, 'bloklangan xabar admin uchun saqlandi');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_reactions WHERE from_id = ?', [$me]), 0, 'bloklanganda like yozilmadi');
    T::text($me, str_repeat('a', 301));
    T::eq(T::lastText($me), Lang::t('uz', 'likemsg.len', ['max' => 300]), 'uzunlik chegarasi');
    T::$tg->reset();
    T::text($me, 'Salom, tabassumingiz chiroyli 😊');
    $n = T::$tg->last($her, 'sendMessage');
    T::eq($n['params']['text'] ?? null, Lang::t('ru', 'likemsg.notify', ['text' => 'Salom, tabassumingiz chiroyli 😊']), 'xabar o‘z tilida yetkazildi');
    T::ok(!empty($n['params']['protect_content']), 'protect_content');
    T::eq($db->val('SELECT kind FROM tb_reactions WHERE from_id = ? AND to_id = ?', [$me, $her]), 'like', 'like yozildi');
    T::eq($db->val('SELECT status FROM tb_like_msgs WHERE from_id = ? AND to_id = ? ORDER BY id DESC LIMIT 1', [$me, $her]), 'delivered', 'xabar holati delivered');
    T::eq(T::user($me)['state'], null, 'holat tozalandi');
    // qabul qiluvchi ro‘yxatda kartada xabarni ko‘radi
    T::$tg->reset();
    T::cb($her, 'lk:l');
    T::ok(str_contains(T::lastText($her), '«Salom, tabassumingiz chiroyli 😊»'), 'likes ro‘yxatida kartada xabar');

    // moderatsiya rejimi
    $me2 = 9122;
    T::register($me2, 'uz', 'Aziz', 'm', 1);
    Settings::set('likemsg_mode', 'moderate');
    T::setAdmins([ADM]);
    T::eq(openCard($me2), $her, 'karta 2');
    T::cb($me2, T::data($me2, 'r:m:'));
    T::$tg->reset();
    T::text($me2, 'Tanishamizmi?');
    T::eq(T::$tg->last($her, 'sendMessage'), null, 'moderatsiyada darhol yetkazilmaydi');
    T::eq(T::lastText(ADM), Lang::t(Lang::norm(T::user(ADM)['lang'] ?? null), 'admin.likemsg_new'), 'admin xabardor');
    $lid = (int)$db->val("SELECT id FROM tb_like_msgs WHERE from_id = ? AND status = 'pending'", [$me2]);
    T::ok($lid > 0, 'pending xabar');
    T::cb(ADM, 'a:lq');
    T::ok(T::data(ADM, 'a:la:' . $lid) !== null, 'admin navbatida xabar');
    T::$tg->reset();
    T::cb(ADM, 'a:la:' . $lid);
    T::ok(str_contains((string)(T::$tg->last($her, 'sendMessage')['params']['text'] ?? ''), 'Tanishamizmi?'), 'admin tasdiqlagach yetkazildi');
    T::cb(ADM, 'a:la:' . $lid);
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_admin_audit WHERE action = 'lmsg_approve'"), 1, 'qayta tasdiqlash ikkinchi marta yetkazmaydi');

    // o‘chiq rejim
    Settings::set('likemsg_mode', 'off');
    $me3 = 9123;
    T::register($me3, 'uz', 'Ali', 'm', 1);
    T::$tg->reset();
    openCard($me3);
    T::eq(T::data($me3, 'r:m:'), null, 'o‘chiq rejimda tugma yo‘q');
    Settings::set('likemsg_mode', 'on');
    Settings::set('likemsg_stopwords', '');
});

$t('tasdiqlash: selfi navbati, admin tasdiqlaydi/rad etadi, rasm o‘zgarsa belgi olinadi', function () {
    T::setAdmins([ADM]);
    $db = App::db();
    $uid = 9130;
    T::register($uid, 'en', 'Kate', 'f', 1);
    T::cb($uid, 'pr:vf');
    $g = json_decode((string)T::user($uid)['state_data'], true)['g'] ?? '';
    T::ok(in_array($g, \TB\Profile::GESTURES, true), 'ishora tanlandi');
    T::ok(str_contains(T::lastText($uid), $g), 'ishora foydalanuvchiga aytildi');
    T::text($uid, 'salom');
    T::eq(T::lastText($uid), Lang::t('en', 'verify.need_photo', ['gesture' => $g]), 'matn emas, rasm kerak');
    T::photo($uid, 'SELFIE1');
    $vid = (int)$db->val("SELECT id FROM tb_verifications WHERE user_id = ? AND status = 'pending'", [$uid]);
    T::ok($vid > 0, 'so‘rov navbatga tushdi');
    T::cb($uid, 'pr:vf');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_verifications WHERE user_id = ?", [$uid]), 1, 'ikkinchi so‘rov ochilmaydi');
    T::$tg->reset();
    T::cb(ADM, 'a:vq');
    $ph = T::$tg->byMethod('sendPhoto');
    T::eq($ph[0]['params']['photo'] ?? null, 'SELFIE1', 'admin selfini ko‘rdi');
    T::ok(!empty($ph[0]['params']['protect_content']), 'selfi protect_content bilan');
    T::eq($ph[1]['params']['photo'] ?? null, 'PH_' . $uid, 'solishtirish uchun anketa rasmi');
    T::cb(ADM, 'a:vr:' . $vid . ':2');
    T::eq(T::lastText($uid), Lang::t('en', 'verify.rejected', ['reason' => Lang::t('en', 'verify.r2')]), 'rad etish sababi o‘z tilida');
    T::eq((int)Users::find($uid)['verified'], 0, 'rad etilganda belgi yo‘q');
    T::cb($uid, 'pr:vf');
    T::photo($uid, 'SELFIE2');
    $vid2 = (int)$db->val("SELECT id FROM tb_verifications WHERE user_id = ? AND status = 'pending'", [$uid]);
    T::cb(ADM, 'a:va:' . $vid2);
    T::eq((int)Users::find($uid)['verified'], 1, 'tasdiqlandi');
    T::eq(T::lastText($uid), Lang::t('en', 'verify.approved'), 'foydalanuvchiga xabar');
    T::ok(str_contains(\TB\Profile::cardText('en', Users::find($uid)), 'Kate, 25 ✅'), 'kartada ✅');
    T::cb(ADM, 'a:va:' . $vid2);
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_admin_audit WHERE action = 'verify.approve' AND target = ?", [(string)$uid]), 1, 'takroriy tasdiq yo‘q');
    // rasm o‘zgarsa belgi olinadi
    T::cb($uid, 'pr:e:photo');
    T::photo($uid, 'NEWPH');
    T::cb($uid, 'e:ph:save');
    T::eq((int)Users::find($uid)['verified'], 0, 'yangi rasm: belgi olindi');
    T::ok(in_array(Lang::t('en', 'verify.reset'), T::texts($uid), true), 'foydalanuvchiga tushuntirildi');
    // admin o‘chirib qo‘ysa tugma yo‘q
    Settings::set('verify_enabled', '0');
    T::$tg->reset();
    T::cb($uid, 'pr:back');
    T::eq(T::data($uid, 'pr:vf'), null, 'tasdiqlash o‘chiq: tugma yo‘q');
    Settings::set('verify_enabled', '1');
});

$t('avto-yashirish: 3 ta turli shikoyat anketani yashiradi, admin qaytaradi', function () {
    T::isolate();
    T::setAdmins([ADM]);
    $db = App::db();
    $bad = 9140;
    T::register($bad, 'uz', 'Spam', 'f', 1);
    foreach ([9141, 9142, 9143] as $i => $r) {
        T::register($r, 'uz', 'R' . $i, 'm', 1);
        T::eq(openCard($r), $bad, "$r: karta");
        $cb = T::data($r, 'r:p:');
        T::ok($cb !== null, 'kartada 🚩 tugmasi');
        T::cb($r, $cb);
        T::$tg->reset();
        T::text($r, 'Pul so‘rayapti, firibgar');
        if ($i < 2) {
            T::eq((int)Users::find($bad)['mod_hidden'], 0, ($i + 1) . ' ta shikoyatda hali yashirilmagan');
        }
    }
    T::eq((int)Users::find($bad)['mod_hidden'], 1, '3-shikoyatda yashirildi');
    T::ok(in_array(Lang::t(Lang::norm(T::user(ADM)['lang'] ?? null), 'admin.autohidden', ['id' => $bad, 'n' => 3]), T::texts(ADM), true), 'admin xabardor');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_admin_audit WHERE action = 'user.autohide' AND target = ?", [(string)$bad]), 1, 'auditda');
    $x = 9144;
    T::register($x, 'uz', 'X', 'm', 1);
    T::eq(openCard($x), null, 'yashirilgan qidiruvda yo‘q');
    T::cb(ADM, 'a:hq:0');
    T::ok(T::data(ADM, 'a:uv:' . $bad) !== null, 'admin yashirilganlar ro‘yxatida');
    T::cb(ADM, 'a:uh:' . $bad);
    T::eq((int)Users::find($bad)['mod_hidden'], 0, 'admin qaytardi');
    // o‘chirilgan bo‘lsa yashirmaydi
    Settings::set('autohide_reports', '0');
    T::ok(!\TB\Chat::autoHide(new \TB\Ctx(ADM, 1, ['message_id' => 1], null), $bad), 'sozlama 0: yashirmaydi');
    Settings::set('autohide_reports', '3');
});

$t('admin: sozlamalar, Premium sovg‘a, foydalanuvchi kartasi', function () {
    T::setAdmins([ADM]);
    $db = App::db();
    T::cb(ADM, 'a:cfg');
    T::cb(ADM, 'a:cf:lm');
    T::eq(Settings::likeMsgMode(), 'moderate', 'rejim: on → moderate');
    T::cb(ADM, 'a:cf:lm');
    T::cb(ADM, 'a:cf:lm');
    T::eq(Settings::likeMsgMode(), 'on', 'rejim aylanadi');
    T::cb(ADM, 'a:cf:age');
    T::text(ADM, '17 40');
    T::eq(T::lastText(ADM), Lang::t(Lang::norm(T::user(ADM)['lang'] ?? null), 'adm.cf_age_bad'), '18 dan past min rad');
    T::text(ADM, '20 45');
    T::eq(Settings::ageRange(), [20, 45], 'yosh chegarasi saqlandi');
    T::cb(ADM, 'a:cf:ah');
    T::text(ADM, '5 14');
    T::eq([Settings::int('autohide_reports'), Settings::int('autohide_days')], [5, 14], 'avto-yashirish saqlandi');
    T::cb(ADM, 'a:cf:sw');
    T::text(ADM, 'aaa, Bbb ,ccc');
    T::eq(Settings::stopwords(), ['aaa', 'bbb', 'ccc'], 'so‘zlar ro‘yxati');
    T::cb(ADM, 'a:cf:sw');
    T::text(ADM, '-');
    T::eq(Settings::stopwords(), [], 'ro‘yxat tozalandi');
    T::cb(ADM, 'a:cf:ln');
    T::ok(!Settings::on('likemsg_links'), 'havola blokini o‘chirish');
    T::cb(ADM, 'a:cf:ln');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_admin_audit WHERE action LIKE 'settings.%'"), 9, 'har o‘zgarish auditda');
    Settings::set('age_min', '18');
    Settings::set('age_max', '99');
    Settings::set('autohide_reports', '3');
    Settings::set('autohide_days', '30');

    $uid = 9150;
    T::register($uid, 'ru', 'Гость', 'm', 1);
    T::cb(ADM, 'a:ug:' . $uid);
    T::text(ADM, '400');
    T::ok(!Users::isPremium(Users::find($uid)), '365 dan ko‘p kun rad');
    T::text(ADM, '3');
    $u = Users::find($uid);
    T::ok(Users::isPremium($u), 'Premium berildi');
    $left = strtotime($u['premium_until'] . ' UTC') - time();
    T::ok($left > 3 * 86400 - 120 && $left <= 3 * 86400 + 5, '3 kun');
    T::ok(str_starts_with(T::lastText($uid), '🎁'), 'foydalanuvchiga o‘z tilida xabar');
    T::$tg->reset();
    T::cb(ADM, 'a:uv:' . $uid);
    T::ok(str_contains(T::lastText(ADM), Lang::t(Lang::norm(T::user(ADM)['lang'] ?? null), 'adm.user_more', [
        'age' => 25, 'goal' => Lang::t(Lang::norm(T::user(ADM)['lang'] ?? null), 'goal.serious'), 'verified' => '—', 'hidden' => '—',
        'reports' => 0, 'likes' => 0, 'matches' => 0, 'seen' => substr((string)T::user($uid)['last_seen_at'], 0, 16),
    ])), 'kartada yosh, maqsad, statistika');
    foreach (['a:uhd:', 'a:uvf:', 'a:ug:'] as $p) {
        T::ok(T::data(ADM, $p . $uid) !== null, "tugma $p");
    }
    T::cb(ADM, 'a:st');
    T::ok(str_contains(T::lastText(ADM), "\n"), 'statistika');
    T::ok(T::data(ADM, 'a:h') !== null, 'statistikadan orqaga');
});
