<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Anonim suhbat. forwardMessage/copyMessage ishlatilmaydi: bot har xabarni yangi xabar
 * sifatida yuboradi, faqat ruxsat etilgan maydonlar (matn, foto file_id, ovoz file_id,
 * stiker file_id, izoh matni) olinadi. entities, forward_origin, contact, username,
 * original message_id uzatilmaydi. protect_content yoqilgan.
 */
final class Chat
{
    public static function kb(string $lang, int $cid): array
    {
        return Kb::inline([[[Lang::t($lang, 'chat.end'), 'c:e:' . $cid], [Lang::t($lang, 'chat.report'), 'c:r:' . $cid]],
            [[Lang::t($lang, 'chat.block'), 'c:b:' . $cid]]]);
    }

    public static function callback(Ctx $ctx, array $p): void
    {
        $a = $p[1] ?? '';
        $id = isset($p[2]) && ctype_digit($p[2]) ? (int)$p[2] : 0;
        switch ($a) {
            case 's':
                self::start($ctx, $id);
                return;
            case 'e':
                $chat = self::memberChat($ctx, $id);
                if (!$chat || $chat['status'] !== 'active') {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $ctx->answer();
                self::end($ctx, $id, 'user');
                return;
            case 'r':
                $chat = self::memberChat($ctx, $id);
                if (!$chat) {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $ctx->answer();
                $other = (int)$chat['user_a'] === $ctx->uid ? (int)$chat['user_b'] : (int)$chat['user_a'];
                if ($chat['status'] === 'active') {
                    self::end($ctx, $id, 'report', false);
                }
                $ctx->setState('report', ['chat' => $id, 'reported' => $other]);
                $ctx->send($ctx->t('report.ask'), Kb::inline([[[$ctx->t('btn.cancel'), 'c:rx']]]));
                return;
            case 'b':
                $chat = self::memberChat($ctx, $id);
                if (!$chat) {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $ctx->answer();
                $other = (int)$chat['user_a'] === $ctx->uid ? (int)$chat['user_b'] : (int)$chat['user_a'];
                Blocks::add($ctx, $other);
                if (($ctx->u['active_chat_id'] ?? null) === null) {
                    Menu::home($ctx, 'chat.blocked');
                }
                return;
            case 'rx':
                if (($ctx->u['state'] ?? '') === 'report') {
                    $ctx->setState(null);
                }
                $ctx->answer();
                Menu::home($ctx, 'report.cancelled');
                return;
        }
        $ctx->answer($ctx->t('err.stale'));
    }

    private static function memberChat(Ctx $ctx, int $id): ?array
    {
        if ($id <= 0) {
            return null;
        }
        $c = App::db()->one('SELECT * FROM tb_chats WHERE id = ? FOR UPDATE', [$id]);
        if (!$c || ((int)$c['user_a'] !== $ctx->uid && (int)$c['user_b'] !== $ctx->uid)) {
            return null;
        }
        return $c;
    }

    public static function start(Ctx $ctx, int $mid): void
    {
        $db = App::db();
        $m = $mid > 0 ? $db->one('SELECT * FROM tb_matches WHERE id = ?', [$mid]) : null;
        if (!$m || ((int)$m['user_a'] !== $ctx->uid && (int)$m['user_b'] !== $ctx->uid)) {
            $ctx->answer($ctx->t('err.stale'));
            return;
        }
        $otherId = (int)$m['user_a'] === $ctx->uid ? (int)$m['user_b'] : (int)$m['user_a'];
        if (!empty($ctx->u['active_chat_id'])) {
            $ctx->answer($ctx->t('chat.already'), true);
            self::remind($ctx);
            return;
        }
        if (Blocks::between($ctx->uid, $otherId)) {
            $ctx->answer($ctx->t('err.unavailable'), true);
            return;
        }
        $other = Users::find($otherId, true);
        if (!Users::isVisible($other)) {
            $ctx->answer($ctx->t('err.unavailable'), true);
            return;
        }
        if (!empty($other['active_chat_id'])) {
            $ctx->answer($ctx->t('chat.partner_busy'), true);
            return;
        }
        $db->exec("INSERT INTO tb_chats (match_id, user_a, user_b, status, started_at) VALUES (?, ?, ?, 'active', UTC_TIMESTAMP())", [$mid, $m['user_a'], $m['user_b']]);
        $cid = $db->lastId();
        $db->exec('UPDATE tb_users SET active_chat_id = ?, state = NULL, state_data = NULL WHERE id IN (?, ?)', [$cid, $ctx->uid, $otherId]);
        $ctx->u['active_chat_id'] = $cid;
        $ctx->answer();
        $ol = Lang::norm($other['lang'] ?? null);
        foreach ([[$ctx->uid, $ctx->lang], [$otherId, $ol]] as [$to, $l]) {
            $ctx->api('sendMessage', ['chat_id' => $to, 'text' => Lang::t($l, 'chat.started'), 'reply_markup' => Kb::remove()], $to);
            $ctx->api('sendMessage', ['chat_id' => $to, 'text' => Lang::t($l, 'chat.warning'), 'reply_markup' => self::kb($l, $cid), 'protect_content' => true], $to);
        }
    }

    public static function remind(Ctx $ctx): void
    {
        $cid = (int)($ctx->u['active_chat_id'] ?? 0);
        $ctx->send($ctx->t('chat.in_chat'), self::kb($ctx->lang, $cid));
    }

    /** Faqat ruxsat etilgan maydonlardan yangi xabar quradi. */
    public static function buildRelay(array $msg, int $to, array $markup): ?array
    {
        $base = ['chat_id' => $to, 'protect_content' => true, 'reply_markup' => $markup];
        $caption = isset($msg['caption']) && is_string($msg['caption']) ? mb_substr($msg['caption'], 0, 1024) : null;
        if (isset($msg['contact']) || isset($msg['location']) || isset($msg['venue']) || isset($msg['poll'])) {
            return null;
        }
        if (isset($msg['text']) && is_string($msg['text'])) {
            return ['sendMessage', $base + ['text' => mb_substr($msg['text'], 0, 4096)]];
        }
        if (($fid = Registration::photoId($msg)) !== null) {
            return ['sendPhoto', $base + ['photo' => $fid] + ($caption !== null && $caption !== '' ? ['caption' => $caption] : [])];
        }
        if (isset($msg['voice']['file_id']) && is_string($msg['voice']['file_id'])) {
            return ['sendVoice', $base + ['voice' => $msg['voice']['file_id']]];
        }
        if (isset($msg['sticker']['file_id']) && is_string($msg['sticker']['file_id'])) {
            return ['sendSticker', $base + ['sticker' => $msg['sticker']['file_id']]];
        }
        return null;
    }

    public static function relay(Ctx $ctx, array $msg): void
    {
        $cid = (int)$ctx->u['active_chat_id'];
        $chat = App::db()->one("SELECT * FROM tb_chats WHERE id = ? AND status = 'active'", [$cid]);
        if (!$chat) {
            $ctx->set(['active_chat_id' => null]);
            Menu::home($ctx);
            return;
        }
        $to = (int)$chat['user_a'] === $ctx->uid ? (int)$chat['user_b'] : (int)$chat['user_a'];
        $toUser = Users::find($to);
        $tl = Lang::norm($toUser['lang'] ?? null);
        $r = self::buildRelay($msg, $to, self::kb($tl, $cid));
        if ($r === null) {
            $ctx->send($ctx->t('chat.unsupported'));
            return;
        }
        $id = Outbox::add($to, $r[0], $r[1], 'relay:' . $ctx->updateId, 3);
        if ($id) {
            $ctx->out[] = $id;
        }
    }

    /** Suhbatni tugatadi. Ikkala a’zoning active_chat_id si tozalanadi. */
    public static function end(Ctx $ctx, int $cid, string $reason, bool $notifySelf = true): bool
    {
        $db = App::db();
        $chat = $db->one('SELECT * FROM tb_chats WHERE id = ? FOR UPDATE', [$cid]);
        if (!$chat || $chat['status'] !== 'active') {
            return false;
        }
        $db->exec("UPDATE tb_chats SET status = 'ended', ended_at = UTC_TIMESTAMP(), ended_by = ?, end_reason = ? WHERE id = ?", [$ctx->uid, $reason, $cid]);
        $db->exec('UPDATE tb_users SET active_chat_id = NULL WHERE active_chat_id = ?', [$cid]);
        $other = (int)$chat['user_a'] === $ctx->uid ? (int)$chat['user_b'] : (int)$chat['user_a'];
        if ($ctx->uid === (int)$chat['user_a'] || $ctx->uid === (int)$chat['user_b']) {
            $ctx->u['active_chat_id'] = null;
        }
        $ou = Users::find($other);
        if ($ou) {
            $ol = Lang::norm($ou['lang'] ?? null);
            $ctx->api('sendMessage', ['chat_id' => $other, 'text' => Lang::t($ol, 'chat.ended_partner'), 'reply_markup' => Menu::keyboard($ol)], $other);
        }
        if ($notifySelf) {
            Menu::home($ctx, 'chat.ended');
        }
        return true;
    }

    /** Admin suspend qilganda: foydalanuvchining faol suhbatini tugatish. */
    public static function endForUser(Ctx $ctx, int $uid): void
    {
        $db = App::db();
        $u = $db->one('SELECT active_chat_id FROM tb_users WHERE id = ?', [$uid]);
        $cid = (int)($u['active_chat_id'] ?? 0);
        if ($cid <= 0) {
            return;
        }
        $chat = $db->one('SELECT * FROM tb_chats WHERE id = ? FOR UPDATE', [$cid]);
        $db->exec("UPDATE tb_chats SET status = 'ended', ended_at = UTC_TIMESTAMP(), ended_by = ?, end_reason = 'admin' WHERE id = ? AND status = 'active'", [$ctx->uid, $cid]);
        $db->exec('UPDATE tb_users SET active_chat_id = NULL WHERE active_chat_id = ?', [$cid]);
        if ($chat) {
            foreach ([(int)$chat['user_a'], (int)$chat['user_b']] as $m) {
                $mu = Users::find($m);
                if ($mu) {
                    $l = Lang::norm($mu['lang'] ?? null);
                    $ctx->api('sendMessage', ['chat_id' => $m, 'text' => Lang::t($l, 'chat.ended_partner'), 'reply_markup' => Menu::keyboard($l)], $m);
                }
            }
        }
    }

    public static function reportInput(Ctx $ctx, array $msg): void
    {
        $text = isset($msg['text']) && is_string($msg['text']) ? trim($msg['text']) : '';
        $len = mb_strlen($text);
        if ($len < 5 || $len > 500) {
            $ctx->send($ctx->t('report.len'), Kb::inline([[[$ctx->t('btn.cancel'), 'c:rx']]]));
            return;
        }
        $d = $ctx->stateData();
        $db = App::db();
        $db->exec(
            "INSERT INTO tb_reports (reporter_id, reported_id, chat_id, reason, status, created_at) VALUES (?, ?, ?, ?, 'open', UTC_TIMESTAMP())",
            [$ctx->uid, (int)($d['reported'] ?? 0), (int)($d['chat'] ?? 0) ?: null, $text]
        );
        $rid = $db->lastId();
        $ctx->setState(null);
        Admin::notify($ctx, 'admin.new_report', ['id' => $rid]);
        self::autoHide($ctx, (int)($d['reported'] ?? 0));
        Menu::home($ctx, 'report.thanks');
    }

    /**
     * Avtomatik moderatsiya: belgilangan kun ichida N ta turli foydalanuvchi shikoyat qilsa,
     * anketa qidiruvdan yashiriladi (foydalanuvchiga aytilmaydi) va adminlar xabardor qilinadi.
     */
    public static function autoHide(Ctx $ctx, int $uid): bool
    {
        $need = Settings::int('autohide_reports');
        if ($uid <= 0 || $need <= 0 || App::isAdmin($uid)) {
            return false;
        }
        $days = max(1, min(365, Settings::int('autohide_days')));
        $db = App::db();
        $n = (int)$db->val(
            "SELECT COUNT(DISTINCT reporter_id) FROM tb_reports WHERE reported_id = ? AND created_at > UTC_TIMESTAMP() - INTERVAL $days DAY",
            [$uid]
        );
        if ($n < $need) {
            return false;
        }
        $hidden = (int)$db->val('SELECT mod_hidden FROM tb_user_ext WHERE user_id = ?', [$uid]);
        if ($hidden === 1) {
            return false;
        }
        Users::updateExt($uid, ['mod_hidden' => 1]);
        $db->exec(
            "INSERT INTO tb_admin_audit (admin_id, action, target, details, created_at) VALUES (0, 'user.autohide', ?, ?, UTC_TIMESTAMP())",
            [(string)$uid, $n . ' reports / ' . $days . 'd']
        );
        Admin::notify($ctx, 'admin.autohidden', ['id' => $uid, 'n' => $n]);
        return true;
    }
}
