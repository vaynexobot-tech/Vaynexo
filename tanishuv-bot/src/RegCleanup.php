<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Ro‘yxatdan o‘tish paytidagi ketma-ket xabarlarni (bot savollari va foydalanuvchi javoblari)
 * profil tasdiqlangach chatdan o‘chiradi. Chat toza qoladi: faqat «Profilingiz tayyor» va bosh menyu.
 *
 * - Foydalanuvchi xabarlari: update kelganda message_id yoziladi.
 * - Bot xabarlari: Outbox yuborganda Telegram qaytargan message_id yoziladi.
 * - Tasdiqlashda deleteMessages (100 tadan) navbatga qo‘yiladi.
 * Telegram 48 soatdan eski xabarlarni o‘chirmaydi, shuning uchun faqat 47 soat ichidagilar olinadi.
 */
final class RegCleanup
{
    public const KEY = '_tb_reg';
    public const TRACKED = ['sendMessage', 'sendPhoto', 'sendMediaGroup'];
    public const MAX_AGE_HOURS = 47;

    public static function finished(array $u): bool
    {
        return ($u['reg_step'] ?? '') === 'done';
    }

    /** Foydalanuvchining ro‘yxat paytidagi xabari. */
    public static function incoming(Ctx $ctx): void
    {
        $mid = $ctx->msg['message_id'] ?? null;
        if (!is_int($mid) || $mid <= 0 || self::finished($ctx->u)) {
            return;
        }
        App::db()->exec(
            'INSERT IGNORE INTO tb_reg_msgs (user_id, message_id, created_at) VALUES (?, ?, UTC_TIMESTAMP())',
            [$ctx->uid, $mid]
        );
    }

    /** Outbox muvaffaqiyatli yuborgan bot xabari. */
    public static function sent(int $chatId, mixed $result): void
    {
        $ids = [];
        if (is_array($result) && isset($result['message_id'])) {
            $ids[] = (int)$result['message_id'];
        } elseif (is_array($result)) {
            foreach ($result as $m) {
                if (is_array($m) && isset($m['message_id'])) {
                    $ids[] = (int)$m['message_id'];
                }
            }
        }
        $ids = array_values(array_filter($ids, static fn(int $i) => $i > 0));
        if (!$ids) {
            return;
        }
        $db = App::db();
        $step = $db->val('SELECT reg_step FROM tb_users WHERE id = ?', [$chatId]);
        if ($step === 'done') {
            // Xabar navbatda kechikib, ro‘yxat allaqachon tugagan bo‘lsa — darhol o‘chiramiz
            foreach ($ids as $mid) {
                Outbox::add($chatId, 'deleteMessage', ['chat_id' => $chatId, 'message_id' => $mid], 'rgd:' . $chatId . ':' . $mid, 6);
            }
            return;
        }
        if ($step === null || $step === false) {
            return;
        }
        foreach ($ids as $mid) {
            $db->exec('INSERT IGNORE INTO tb_reg_msgs (user_id, message_id, created_at) VALUES (?, ?, UTC_TIMESTAMP())', [$chatId, $mid]);
        }
    }

    /** Profil tasdiqlanganda: yozilgan barcha xabarlarni o‘chirishni navbatga qo‘yadi. */
    public static function purge(Ctx $ctx): int
    {
        $db = App::db();
        $ids = array_map('intval', array_column($db->all(
            'SELECT message_id FROM tb_reg_msgs WHERE user_id = ? AND created_at > UTC_TIMESTAMP() - INTERVAL ' . self::MAX_AGE_HOURS . ' HOUR ORDER BY message_id',
            [$ctx->uid]
        ), 'message_id'));
        $cbMid = $ctx->cb['message']['message_id'] ?? null;
        if (is_int($cbMid) && $cbMid > 0 && !in_array($cbMid, $ids, true)) {
            $ids[] = $cbMid;
            sort($ids);
        }
        foreach (array_chunk($ids, 100) as $chunk) {
            $ctx->api('deleteMessages', ['chat_id' => $ctx->uid, 'message_ids' => $chunk]);
        }
        $db->exec('DELETE FROM tb_reg_msgs WHERE user_id = ?', [$ctx->uid]);
        return count($ids);
    }
}
