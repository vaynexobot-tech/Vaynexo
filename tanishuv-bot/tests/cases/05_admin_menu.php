<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Cron;
use TB\Lang;
use TB\Menu;

const ADM = 9000001;
const ADM2 = 9000002;

$t('admin: har admin callback va amalda ruxsat tekshiriladi', function () {
    $x = 5001;
    T::register($x, 'uz', 'Oddiy', 'm', 1);
    $victim = 5002;
    T::register($victim, 'uz', 'Qurbon', 'f', 1);
    $db = App::db();
    T::$tg->reset();
    T::text($x, '/admin');
    T::eq(T::lastText($x), Lang::t('uz', 'cmd.unknown'), 'oddiy foydalanuvchiga /admin ochilmadi');
    $pid = (int)$db->val("SELECT id FROM tb_products WHERE code='premium_1'");
    $calls = ['a:h', 'a:u:0', 'a:uf', 'a:uv:' . $victim, 'a:us:' . $victim, 'a:rp:0', 'a:rd:1', 'a:pm', 'a:bo', 'a:pe:' . $pid, 'a:pd:' . $pid,
        'a:st', 'a:bc', 'a:bn', 'a:by:1', 'a:bx:1', 'a:me', 'a:mi:search', 'a:mr:search', 'a:mm:search', 'a:mn', 'a:mp', 'a:mv', 'a:mx', 'a:md:search',
        'a:bk', 'a:bks', 'a:bkc:0', 'a:bka', 'a:bkd:1', 'a:bkp', 'a:bkn', 'a:bkh', 'a:bkt',
        'a:vq', 'a:va:1', 'a:vr:1:1', 'a:lq', 'a:la:1', 'a:lr:1', 'a:hq:0', 'a:uh:' . $victim, 'a:uhd:' . $victim,
        'a:uvf:' . $victim, 'a:uvu:' . $victim, 'a:ug:' . $victim, 'a:cfg', 'a:cf:lm', 'a:cf:ln', 'a:cf:vf', 'a:cf:age', 'a:cf:ah', 'a:cf:sw'];
    foreach ($calls as $c) {
        T::$tg->reset();
        T::cb($x, $c);
        $ans = T::$tg->byMethod('answerCallbackQuery');
        T::eq($ans[0]['params']['text'] ?? null, Lang::t('uz', 'err.no_access'), "$c: ruxsat yo‘q");
        T::eq(T::user($x)['state'], null, "$c: admin holati ochilmadi");
    }
    T::eq(T::user($victim)['status'], 'active', 'oddiy foydalanuvchi suspend qila olmadi');
    T::eq($db->setting('menu_draft:' . $x), null, 'menyu qoralamasi yaratilmadi');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_admin_audit WHERE admin_id = ?', [$x]), 0, 'audit da begona amal yo‘q');

    // Admin uchun ishlaydi
    T::$tg->reset();
    T::text(ADM, '/admin');
    T::ok(T::data(ADM, 'a:u:0') !== null, 'admin panel ochildi (ro‘yxatdan o‘tmagan admin ham)');
    T::cb(ADM, 'a:us:' . $victim);
    T::eq(T::user($victim)['status'], 'suspended', 'admin suspend qildi');
    T::cb(ADM, 'a:ur:' . $victim);
    T::eq(T::user($victim)['status'], 'active', 'admin tikladi');
    T::cb(ADM, 'a:uf');
    T::text(ADM, (string)$victim);
    T::ok(str_contains(T::lastText(ADM), (string)$victim), 'Telegram ID bo‘yicha qidirish');
    T::cb(ADM, 'a:u:0');
    T::ok(T::data(ADM, 'a:uv:') !== null, 'sahifalangan ro‘yxat');
    T::cb(ADM, 'a:st');
    T::ok(str_contains(T::lastText(ADM), 'XTR'), 'statistika');
});

$t('admin: kechiktirilgan matn bosqichida ruxsat qayta tekshiriladi', function () {
    $db = App::db();
    $pid = (int)$db->val("SELECT id FROM tb_products WHERE code='premium_1'");
    $price = (int)$db->val('SELECT price_xtr FROM tb_products WHERE id = ?', [$pid]);
    T::cb(ADM2, 'a:pe:' . $pid);
    T::eq(T::user(ADM2)['state'], 'adm:price', 'narx kiritish bosqichi ochildi');
    T::setAdmins([ADM]); // ADM2 config dan olib tashlandi
    T::text(ADM2, '1');
    T::eq((int)$db->val('SELECT price_xtr FROM tb_products WHERE id = ?', [$pid]), $price, 'olib tashlangan admin narxni o‘zgartira olmadi');
    T::eq(T::user(ADM2)['state'], null, 'admin holati tozalandi');
    T::setAdmins([ADM, ADM2]);
    T::cb(ADM2, 'a:pe:' . $pid);
    T::text(ADM2, '27');
    T::eq((int)$db->val('SELECT price_xtr FROM tb_products WHERE id = ?', [$pid]), 27, 'admin narxni o‘zgartirdi');
    T::cb(ADM2, 'a:pe:' . $pid);
    T::text(ADM2, '25');
    $boost = (int)$db->val("SELECT id FROM tb_products WHERE code='boost'");
    T::cb(ADM, 'a:pd:' . $boost);
    T::text(ADM, '2');
    T::eq((int)$db->val('SELECT days FROM tb_products WHERE id = ?', [$boost]), 2, 'boost muddati o‘zgardi');
    T::cb(ADM, 'a:pd:' . $boost);
    T::text(ADM, '1');

    // Broadcast matn kiritish o‘rtasida admin olib tashlanadi
    T::cb(ADM2, 'a:bn');
    T::text(ADM2, 'uz matn');
    T::setAdmins([ADM]);
    T::text(ADM2, 'ru text');
    T::eq(T::user(ADM2)['state'], null, 'broadcast oqimi to‘xtadi');
    T::eq((int)$db->val('SELECT COUNT(*) FROM tb_broadcasts WHERE admin_id = ?', [ADM2]), 0, 'broadcast yaratilmadi');
});

$t('admin: shikoyatlar navbati va "Ko‘rib chiqildi"', function () {
    $db = App::db();
    $db->exec("INSERT INTO tb_reports (reporter_id, reported_id, chat_id, reason, status, created_at) VALUES (11, 22, NULL, 'test reason', 'open', UTC_TIMESTAMP())");
    $rid = $db->lastId();
    T::$tg->reset();
    T::cb(ADM, 'a:rp:0');
    $txt = T::lastText(ADM);
    T::ok(str_contains($txt, 'test reason') && str_contains($txt, '11') && str_contains($txt, '22'), 'sabab va tomonlar ID si ko‘rinadi');
    T::cb(ADM, 'a:rd:' . $rid);
    T::eq($db->val('SELECT status FROM tb_reports WHERE id = ?', [$rid]), 'reviewed', 'ko‘rib chiqildi');
});

$t('admin: broadcast preview, tasdiq, CRON 30 tadan, o‘z tilida; admin olib tashlansa bekor', function () {
    $db = App::db();
    T::setAdmins([ADM, ADM2]);
    T::cb(ADM, 'a:bn');
    T::text(ADM, 'Salom hammaga');
    T::text(ADM, 'Привет всем');
    T::$tg->reset();
    T::text(ADM, 'Hello everyone');
    $bid = (int)$db->val('SELECT MAX(id) FROM tb_broadcasts');
    T::eq($db->val('SELECT status FROM tb_broadcasts WHERE id = ?', [$bid]), 'draft', 'tasdiqsiz draft');
    $tx = implode("\n", T::texts(ADM));
    T::ok(str_contains($tx, 'Salom hammaga') && str_contains($tx, 'Привет всем') && str_contains($tx, 'Hello everyone'), 'uch tildagi preview');
    T::cb(ADM, 'a:by:' . $bid);
    T::eq($db->val('SELECT status FROM tb_broadcasts WHERE id = ?', [$bid]), 'queued', 'tasdiqlandi');
    $users = (int)$db->val('SELECT COUNT(*) FROM tb_users WHERE blocked_bot = 0 AND lang IS NOT NULL');
    $n1 = Cron::broadcastBatch();
    T::eq($n1, min(30, $users), 'bitta partiya 30 ta');
    while (Cron::broadcastBatch() >= 0) {
    }
    T::eq($db->val('SELECT status FROM tb_broadcasts WHERE id = ?', [$bid]), 'done', 'yakunlandi');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_outbox WHERE dedupe_key LIKE ?", ['bc:' . $bid . ':%']), $users, 'har foydalanuvchiga bitta');
    $ru = $db->val("SELECT payload FROM tb_outbox WHERE dedupe_key = ?", ['bc:' . $bid . ':1002']);
    T::ok(str_contains((string)$ru, 'Привет всем'), 'rus foydalanuvchiga ruscha');
    $en = $db->val("SELECT payload FROM tb_outbox WHERE dedupe_key = ?", ['bc:' . $bid . ':1003']);
    T::ok(str_contains((string)$en, 'Hello everyone'), 'ingliz foydalanuvchiga inglizcha');

    // Ikkinchi broadcast: yaratgan admin config dan olib tashlanadi → CRON bekor qiladi
    T::cb(ADM2, 'a:bn');
    T::text(ADM2, 'a');
    T::text(ADM2, 'b');
    T::text(ADM2, 'c');
    $b2 = (int)$db->val('SELECT MAX(id) FROM tb_broadcasts');
    T::cb(ADM2, 'a:by:' . $b2);
    T::setAdmins([ADM]);
    $st = Cron::run(microtime(true) + 10);
    T::eq($db->val('SELECT status FROM tb_broadcasts WHERE id = ?', [$b2]), 'cancelled', 'admin olib tashlangani uchun bekor qilindi');
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_outbox WHERE dedupe_key LIKE ?", ['bc:' . $b2 . ':%']), 0, 'hech kimga yuborilmadi');
    T::eq($st['broadcast_cancelled'], 1, 'cron statistikasi');
});

$t('menu: rename, alias, add, move, text, action, preview, save va version conflict', function () {
    $db = App::db();
    T::setAdmins([ADM, ADM2]);
    $u = 5101;
    T::register($u, 'uz', 'Menyu', 'm', 1);
    $oldUz = Lang::t('uz', 'menu.search');

    // Rename (3 til)
    T::cb(ADM, 'a:me');
    T::cb(ADM, 'a:mr:search');
    T::text(ADM, '🔎 Qidiruv');
    T::text(ADM, '🔎 Поиск');
    T::text(ADM, '🔎 Search');
    // Saqlash previewsiz rad etiladi
    T::cb(ADM, 'a:mv');
    T::eq(Menu::live()[0]['label']['uz'], $oldUz, 'previewsiz saqlanmadi');
    // Yangi tugma (matn)
    T::cb(ADM, 'a:mn');
    T::text(ADM, '📰 Yangiliklar');
    T::text(ADM, '📰 Новости');
    T::text(ADM, '📰 News');
    $draft = json_decode((string)$db->setting('menu_draft:' . ADM), true);
    $new = end($draft['items']);
    T::ok(str_starts_with($new['id'], 'c'), 'yangi tugmaning ichki ID si nomdan mustaqil: ' . $new['id']);
    T::cb(ADM, 'a:ms:' . $new['id'] . ':text');
    T::text(ADM, 'Bugungi yangilik');
    T::text(ADM, 'Новость дня');
    T::text(ADM, 'News of the day');
    // Joyini o‘zgartirish
    T::cb(ADM, 'a:mm:' . $new['id']);
    T::text(ADM, '4 1');
    T::ok(str_contains(T::lastText(ADM), Lang::t('uz', 'adm.menu_pos_busy')), 'band joy rad etildi');
    T::text(ADM, '13 1');
    T::ok(str_contains(T::lastText(ADM), Lang::t('uz', 'adm.menu_pos_bad')), '13-qator rad etildi');
    T::text(ADM, '5 3');
    // Asosiy bo‘limni o‘chirish / amalini o‘zgartirish rad
    T::cb(ADM, 'a:md:search');
    T::cb(ADM, 'a:ms:premium:text');
    $draft = json_decode((string)$db->setting('menu_draft:' . ADM), true);
    T::ok(\TB\Menu::findItem($draft['items'], 'search') !== null, 'asosiy bo‘lim o‘chmadi');
    T::eq(\TB\Menu::findItem($draft['items'], 'premium')['action'], 'premium', 'asosiy action buzilmadi');
    // Takroriy nom rad
    T::cb(ADM, 'a:mr:' . $new['id']);
    T::text(ADM, '🔎 Qidiruv');
    T::ok(str_contains(T::lastText(ADM), Lang::t('uz', 'adm.menu_label_duplicate')), 'takroriy nom rad etildi');
    T::cb(ADM, 'a:me');

    // ADM2 ham eski versiyadan qoralama ochadi
    T::cb(ADM2, 'a:me');
    T::cb(ADM2, 'a:mr:likes');
    T::text(ADM2, 'L1');
    T::text(ADM2, 'L2');
    T::text(ADM2, 'L3');

    // Preview → Save
    T::$tg->reset();
    T::cb(ADM, 'a:mp');
    $pv = T::lastText(ADM);
    T::ok(str_contains($pv, '🔎 Qidiruv') && str_contains($pv, '🔎 Поиск') && str_contains($pv, '🔎 Search') && str_contains($pv, '📰 News'), 'uch tildagi preview');
    $ver = Menu::version();
    T::cb(ADM, 'a:mv');
    T::eq(Menu::version(), $ver + 1, 'versiya oshdi');
    Menu::reset();
    T::eq(Menu::findItem(Menu::live(), 'search')['label']['ru'], '🔎 Поиск', 'jonli menyu yangilandi');
    $it = Menu::findItem(Menu::live(), $new['id']);
    T::eq([$it['row'], $it['col'], $it['action']], [5, 3, 'text'], 'yangi tugma joyi va amali');

    // Foydalanuvchi: yangi nom, eski nom (alias) va matnli tugma
    T::$tg->reset();
    T::text($u, '🔎 Qidiruv');
    T::ok(T::data($u, 's:m') !== null, 'yangi nom bilan qidiruv ochildi');
    T::$tg->reset();
    T::text($u, $oldUz);
    T::ok(T::data($u, 's:m') !== null, 'eski nom alias orqali ishladi');
    T::eq($db->val('SELECT item_id FROM tb_menu_aliases WHERE label = ?', [$oldUz]), 'search', 'alias saqlangan');
    T::text($u, '📰 Yangiliklar');
    T::eq(T::lastText($u), 'Bugungi yangilik', 'matnli tugma');
    $kb = T::lastReplyKeyboard($u) ?? [];
    T::text($u, '/start');
    $kb = T::lastReplyKeyboard($u);
    T::eq($kb[0][0]['text'], '🔎 Qidiruv', 'klaviatura yangi nom bilan');
    T::eq(end($kb)[0]['text'], '📰 Yangiliklar', 'yangi tugma oxirgi qatorda');

    // Version conflict: ADM2 eski qoralamani saqlay olmaydi
    T::cb(ADM2, 'a:mp');
    T::cb(ADM2, 'a:mv');
    Menu::reset();
    T::eq(Menu::version(), $ver + 1, 'eski qoralama versiyani oshirmadi');
    T::eq(Menu::findItem(Menu::live(), 'likes')['label']['uz'], Lang::t('uz', 'menu.likes'), 'eski qoralama yangi menyuni bosib ketmadi');
    T::ok(str_contains(T::lastText(ADM2), 'v' . $ver), 'conflict xabari');

    // Actionni o‘zgartirish: nom o‘zgarsa ham vazifa ishlaydi
    T::cb(ADM, 'a:me');
    T::cb(ADM, 'a:ms:' . $new['id'] . ':support');
    T::cb(ADM, 'a:mr:' . $new['id']);
    T::text(ADM, '🆘 Yordam');
    T::text(ADM, '🆘 Помощь');
    T::text(ADM, '🆘 Help');
    T::cb(ADM, 'a:mp');
    T::cb(ADM, 'a:mv');
    Menu::reset();
    T::text($u, '🆘 Yordam');
    T::ok(str_contains(T::lastText($u), '@support_test'), 'yangi action ishladi');
    T::text($u, '📰 Yangiliklar');
    T::ok(str_contains(T::lastText($u), '@support_test'), 'eski nom alias orqali yangi actionga boradi');

    // 24 tugma chegarasi
    T::cb(ADM, 'a:me');
    $d = json_decode((string)$db->setting('menu_draft:' . ADM), true);
    for ($i = count($d['items']); $i < 24; $i++) {
        $d['items'][] = ['id' => 'cx' . $i, 'action' => 'terms', 'label' => ['uz' => "U$i", 'ru' => "R$i", 'en' => "E$i"], 'text' => null, 'row' => intdiv($i, 3) + 1, 'col' => $i % 3 + 1];
    }
    // joylarni qayta taqsimlash
    foreach ($d['items'] as $k => &$it2) {
        $it2['row'] = intdiv($k, 3) + 1;
        $it2['col'] = $k % 3 + 1;
    }
    unset($it2);
    $db->setSetting('menu_draft:' . ADM, json_encode($d));
    T::eq(\TB\MenuEditor::validate($d['items']), null, '24 ta tugma 1–12 qator × 1–3 ustunda yaroqli');
    T::cb(ADM, 'a:mn');
    T::ok(str_contains(T::lastText(ADM), '24'), '25-tugma rad etildi');
    T::cb(ADM, 'a:mx');
    T::eq($db->setting('menu_draft:' . ADM), null, 'qoralama bekor qilindi');
});
