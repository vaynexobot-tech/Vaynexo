<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Foydalanuvchini qaytaruvchi eslatmalar (CRON orqali, past ustuvorlik bilan):
 *  - likes: oxirgi tashrifidan keyin yangi like olgan (24 soatda ko‘pi bilan 1 ta);
 *  - inactive: 3–30 kun kirmagan (7 kunda ko‘pi bilan 1 ta).
 * Botni bloklaganlar va to‘xtatilgan/yashirin profillar o‘tkazib yuboriladi.
 */
final class Retention
{
    public const BATCH = 100;

    public static function run(): int
    {
        if (!Settings::on('retention')) {
            return 0;
        }
        return self::likes() + self::inactive();
    }

    private static function base(): string
    {
        return "u.reg_step = 'done' AND u.age_confirmed = 1 AND u.status = 'active' AND u.blocked_bot = 0 AND u.lang IS NOT NULL AND u.active_chat_id IS NULL";
    }

    private static function likes(): int
    {
        $rows = App::db()->all(
            "SELECT u.id, u.lang, COUNT(DISTINCT r.from_id) AS n
             FROM tb_users u
             JOIN tb_reactions r ON r.to_id = u.id AND r.kind IN ('like','super') AND r.created_at > u.last_seen_at
             JOIN tb_users f ON f.id = r.from_id AND f.status = 'active' AND f.reg_step = 'done'
             LEFT JOIN tb_notices n ON n.user_id = u.id AND n.kind = 'likes'
             WHERE " . self::base() . "
               AND u.last_seen_at < UTC_TIMESTAMP() - INTERVAL 6 HOUR
               AND (n.sent_at IS NULL OR n.sent_at < UTC_TIMESTAMP() - INTERVAL 24 HOUR)
             GROUP BY u.id, u.lang
             LIMIT " . self::BATCH
        );
        return self::send($rows, 'likes', 'retention.likes');
    }

    private static function inactive(): int
    {
        $rows = App::db()->all(
            "SELECT u.id, u.lang, 0 AS n
             FROM tb_users u
             LEFT JOIN tb_notices n ON n.user_id = u.id AND n.kind = 'inactive'
             WHERE " . self::base() . "
               AND u.last_seen_at < UTC_TIMESTAMP() - INTERVAL 3 DAY
               AND u.last_seen_at > UTC_TIMESTAMP() - INTERVAL 30 DAY
               AND (n.sent_at IS NULL OR n.sent_at < UTC_TIMESTAMP() - INTERVAL 7 DAY)
             LIMIT " . self::BATCH
        );
        return self::send($rows, 'inactive', 'retention.inactive');
    }

    private static function send(array $rows, string $kind, string $key): int
    {
        $db = App::db();
        $sent = 0;
        foreach ($rows as $r) {
            $uid = (int)$r['id'];
            $l = Lang::norm($r['lang']);
            $db->exec(
                'INSERT INTO tb_notices (user_id, kind, sent_at) VALUES (?, ?, UTC_TIMESTAMP())
                 ON DUPLICATE KEY UPDATE sent_at = VALUES(sent_at)',
                [$uid, $kind]
            );
            $id = Outbox::add(
                $uid,
                'sendMessage',
                ['chat_id' => $uid, 'text' => Lang::t($l, $key, ['n' => (int)$r['n']]), 'reply_markup' => Menu::keyboard($l)],
                'rt:' . $kind . ':' . $uid . ':' . gmdate('YmdH'),
                9
            );
            if ($id) {
                $sent++;
            }
        }
        return $sent;
    }
}
