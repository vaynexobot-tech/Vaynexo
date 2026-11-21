<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\App;
use TB\Lang;

function makeMatch(int $a, int $b): int
{
    $db = App::db();
    $db->exec("INSERT IGNORE INTO tb_reactions (from_id, to_id, kind, created_at) VALUES (?, ?, 'like', UTC_TIMESTAMP()), (?, ?, 'like', UTC_TIMESTAMP())", [$a, $b, $b, $a]);
    $db->exec('INSERT IGNORE INTO tb_matches (user_a, user_b, created_at) VALUES (?, ?, UTC_TIMESTAMP())', [min($a, $b), max($a, $b)]);
    return (int)$db->val('SELECT id FROM tb_matches WHERE user_a = ? AND user_b = ?', [min($a, $b), max($a, $b)]);
}

$t('chat: faqat match a’zolari boshlaydi/tugatadi, bir vaqtda bitta suhbat', function () {
    $a = 4001;
    $b = 4002;
    $c = 4003;
    T::register($a, 'uz', 'Anvar', 'm', 1);
    T::register($b, 'ru', 'Bonu', 'f', 1);
    T::register($c, 'en', 'Carl', 'm', 1);
    $mid = makeMatch($a, $b);
    $mid2 = makeMatch($a, $c);
    $db = App::db();

    T::cb($c, 'c:s:' . $mid);
    T::eq($db->val('SELECT COUNT(*) FROM tb_chats'), 0, 'begona (C) A–B matchida suhbat ocholmadi');
    T::cb($a, 'c:s:' . $mid);
    $cid = (int)T::user($a)['active_chat_id'];
    T::ok($cid > 0, 'A suhbat boshladi');
    T::eq((int)T::user($b)['active_chat_id'], $cid, 'B ham shu suhbatda');
    T::ok(str_contains(T::lastText($b), mb_substr(Lang::t('ru', 'chat.warning'), 0, 20)), 'B ga ogohlantirish o‘z tilida');
    T::eq(T::data($a, 'c:e:'), 'c:e:' . $cid, '"Tugatish" inline tugmasi');
    T::eq(T::data($a, 'c:r:'), 'c:r:' . $cid, '"Shikoyat" inline tugmasi');
    T::eq(T::data($a, 'blk'), null, 'oddiy foydalanuvchiga Bloklash tugmasi yo‘q');

    T::cb($a, 'c:s:' . $mid2);
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_chats WHERE status='active'"), 1, 'A ikkinchi suhbat ocholmadi');
    T::cb($c, 'c:s:' . $mid2);
    T::eq((int)$db->val("SELECT COUNT(*) FROM tb_chats WHERE status='active'"), 1, 'C band A bilan suhbat ocholmadi');

    T::cb($c, 'c:e:' . $cid);
    T::eq($db->val('SELECT status FROM tb_chats WHERE id = ?', [$cid]), 'active', 'begona suhbatni tugata olmadi');
    T::cb($b, 'c:e:' . $cid);
    T::eq($db->val('SELECT status FROM tb_chats WHERE id = ?', [$cid]), 'ended', 'a’zo (B) tugatdi');
    T::eq(T::user($a)['active_chat_id'], null, 'A ozod');
    T::eq(T::user($b)['active_chat_id'], null, 'B ozod');
    T::ok(T::lastReplyKeyboard($a) !== null, 'tugagach bosh menyu qaytdi');
});

$t('chat: anonim relay metadata ni olib tashlaydi (forward/copy yo‘q, protect_content)', function () {
    $a = 4101;
    $b = 4102;
    T::register($a, 'uz', 'Rustam', 'm', 1);
    T::register($b, 'uz', 'Dilnoza', 'f', 1);
    $mid = makeMatch($a, $b);
    T::cb($a, 'c:s:' . $mid);
    $cid = (int)T::user($a)['active_chat_id'];
    T::$tg->reset();

    $meta = [
        'forward_origin' => ['type' => 'user', 'sender_user' => ['id' => 777, 'username' => 'secret_origin']],
        'forward_from' => ['id' => 777],
        'reply_to_message' => ['message_id' => 1],
        'entities' => [['type' => 'text_mention', 'offset' => 0, 'length' => 5, 'user' => ['id' => $a, 'username' => 'user' . $a]]],
        'via_bot' => ['id' => 1],
    ];
    T::send(T::msgUpdate($a, ['text' => 'Salom qalesan'] + $meta));
    T::photo($a, 'PHOTO_FID', ['caption' => 'rasm', 'caption_entities' => [['type' => 'bold', 'offset' => 0, 'length' => 2]]] + $meta);
    T::send(T::msgUpdate($a, ['voice' => ['file_id' => 'VOICE_FID', 'duration' => 3]]));
    T::send(T::msgUpdate($a, ['sticker' => ['file_id' => 'STICKER_FID', 'emoji' => '🙂']]));
    T::send(T::msgUpdate($a, ['contact' => ['phone_number' => '+998901234567', 'first_name' => 'A']]));

    $toB = T::$tg->to($b);
    T::eq(array_column($toB, 'method'), ['sendMessage', 'sendPhoto', 'sendVoice', 'sendSticker'], 'B ga 4 ta yangi xabar (kontakt uzatilmadi)');
    $allowed = ['chat_id', 'protect_content', 'reply_markup', 'text', 'photo', 'caption', 'voice', 'sticker'];
    foreach ($toB as $c) {
        T::eq(array_values(array_diff(array_keys($c['params']), $allowed)), [], $c['method'] . ': faqat ruxsat etilgan maydonlar');
        T::eq($c['params']['protect_content'] ?? null, true, $c['method'] . ': protect_content');
        $json = json_encode($c['params']);
        T::ok(!str_contains($json, 'secret_origin') && !str_contains($json, 'user' . $a) && !str_contains($json, (string)$a), $c['method'] . ': sender/username/ID yo‘q');
        T::ok(!isset($c['params']['entities']) && !isset($c['params']['caption_entities']) && !isset($c['params']['message_id']) && !isset($c['params']['from_chat_id']), $c['method'] . ': entities / message_id yo‘q');
    }
    T::eq($toB[0]['params']['text'], 'Salom qalesan', 'matn yetkazildi');
    T::eq($toB[1]['params']['photo'], 'PHOTO_FID', 'foto file_id');
    T::eq($toB[1]['params']['caption'], 'rasm', 'izoh matni');
    T::eq($toB[2]['params']['voice'], 'VOICE_FID', 'ovozli xabar');
    T::eq($toB[3]['params']['sticker'], 'STICKER_FID', 'stiker');
    T::eq(count(T::$tg->byMethod('forwardMessage')) + count(T::$tg->byMethod('copyMessage')), 0, 'forwardMessage/copyMessage ishlatilmadi');
    T::eq(T::lastText($a), Lang::t('uz', 'chat.unsupported'), 'kontakt uchun ogohlantirish');
    // Yuborilgan relay payload lari {} bilan tozalangan
    $left = (int)App::db()->val("SELECT COUNT(*) FROM tb_outbox WHERE dedupe_key LIKE 'relay:%' AND payload <> '{}'");
    T::eq($left, 0, 'chat matni outbox da saqlanib qolmadi');
    T::eq((int)App::db()->val("SELECT COUNT(*) FROM tb_outbox WHERE payload LIKE '%Salom qalesan%'"), 0, 'matn bazada yo‘q');
});

$t('chat: shikoyat suhbatni tugatadi, sabab 5–500, admin navbatiga tushadi', function () {
    $a = 4201;
    $b = 4202;
    T::register($a, 'uz', 'Sardor', 'm', 1);
    T::register($b, 'en', 'Emma', 'f', 1);
    $mid = makeMatch($a, $b);
    T::cb($a, 'c:s:' . $mid);
    $cid = (int)T::user($a)['active_chat_id'];
    T::cb($b, 'c:r:' . $cid);
    T::eq(App::db()->val('SELECT status FROM tb_chats WHERE id = ?', [$cid]), 'ended', 'shikoyat suhbatni tugatdi');
    T::eq(T::user($a)['active_chat_id'], null, 'A ozod');
    T::eq(T::user($b)['state'], 'report', 'B dan sabab so‘raldi');
    T::text($b, 'abc');
    T::eq((int)App::db()->val('SELECT COUNT(*) FROM tb_reports'), 0, '3 belgili sabab rad etildi');
    T::text($b, str_repeat('x', 501));
    T::eq((int)App::db()->val('SELECT COUNT(*) FROM tb_reports'), 0, '501 belgili sabab rad etildi');
    T::$tg->reset();
    T::text($b, 'He was rude to me');
    $r = App::db()->one('SELECT * FROM tb_reports ORDER BY id DESC LIMIT 1');
    T::eq([(int)$r['reporter_id'], (int)$r['reported_id'], $r['status'], $r['reason']], [$b, $a, 'open', 'He was rude to me'], 'shikoyat ochiq navbatda');
    T::ok(count(T::$tg->to(9000001)) > 0, 'admin xabardor qilindi');
    T::eq(T::user($b)['state'], null, 'holat tozalandi');
    // A shu suhbatda emas: matn relay qilinmaydi
    T::$tg->reset();
    T::text($a, 'hello?');
    T::eq(count(T::$tg->to($b)), 0, 'tugagan suhbatga xabar o‘tmadi');
});
