<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

final class Cron
{
    public const BROADCAST_BATCH = 30;

    public static function run(float $deadline): array
    {
        $db = App::db();
        $st = ['expired_orders' => 0, 'expired_pending' => 0, 'broadcast_enqueued' => 0, 'broadcast_cancelled' => 0, 'sent' => 0, 'cleaned' => 0, 'retention' => 0];
        if (!$db->getLock('cron', 0)) {
            return ['skipped' => 'locked'];
        }
        try {
            $st['expired_orders'] = $db->exec("UPDATE tb_orders SET status = 'expired' WHERE status = 'pending' AND expires_at <= UTC_TIMESTAMP()");
            $st['expired_pending'] = $db->exec("UPDATE tb_bank_pending SET status = 'expired' WHERE status = 'pending' AND expires_at <= UTC_TIMESTAMP()");

            foreach ($db->all("SELECT id, admin_id FROM tb_broadcasts WHERE status = 'queued' ORDER BY id") as $b) {
                if (!App::isAdmin((int)$b['admin_id'])) {
                    $st['broadcast_cancelled'] += $db->exec(
                        "UPDATE tb_broadcasts SET status = 'cancelled', cancel_reason = 'admin_removed', finished_at = UTC_TIMESTAMP() WHERE id = ? AND status = 'queued'",
                        [$b['id']]
                    );
                }
            }
            $batches = 0;
            while ($batches < 40 && microtime(true) < $deadline - 3) {
                $n = self::broadcastBatch();
                if ($n < 0) {
                    break;
                }
                $st['broadcast_enqueued'] += $n;
                $batches++;
                // Yuborish ham navbat bilan: har partiyadan keyin outbox ni yuboramiz
                $st['sent'] += Outbox::process(min($deadline - 2, microtime(true) + 3), 60);
            }
            if (microtime(true) < $deadline - 4) {
                try {
                    $st['retention'] = Retention::run();
                } catch (\Throwable $e) {
                    Log::error('retention', $e);
                }
            }
            $st['sent'] += Outbox::process($deadline - 1);
            if (microtime(true) < $deadline) {
                $st['cleaned'] = self::cleanup();
            }
        } finally {
            $db->releaseLock('cron');
        }
        return $st;
    }

    /** Bitta broadcastdan 30 ta foydalanuvchini navbatga qo‘yadi. -1 = ish yo‘q. */
    public static function broadcastBatch(): int
    {
        return App::db()->tx(static function (Db $db): int {
            $b = $db->one("SELECT * FROM tb_broadcasts WHERE status = 'queued' ORDER BY id LIMIT 1 FOR UPDATE");
            if (!$b) {
                return -1;
            }
            if (!App::isAdmin((int)$b['admin_id'])) {
                $db->exec("UPDATE tb_broadcasts SET status = 'cancelled', cancel_reason = 'admin_removed', finished_at = UTC_TIMESTAMP() WHERE id = ?", [$b['id']]);
                return 0;
            }
            $users = $db->all(
                'SELECT id, lang FROM tb_users WHERE id > ? AND blocked_bot = 0 AND lang IS NOT NULL ORDER BY id LIMIT ' . self::BROADCAST_BATCH,
                [(int)$b['cursor_user_id']]
            );
            $last = (int)$b['cursor_user_id'];
            $n = 0;
            foreach ($users as $u) {
                $l = Lang::norm($u['lang']);
                $text = (string)$b['text_' . $l];
                if (Outbox::add((int)$u['id'], 'sendMessage', ['chat_id' => (int)$u['id'], 'text' => $text], 'bc:' . $b['id'] . ':' . $u['id'], 8)) {
                    $n++;
                }
                $last = (int)$u['id'];
            }
            if (count($users) < self::BROADCAST_BATCH) {
                $db->exec("UPDATE tb_broadcasts SET cursor_user_id = ?, enqueued = enqueued + ?, status = 'done', finished_at = UTC_TIMESTAMP() WHERE id = ?", [$last, $n, $b['id']]);
            } else {
                $db->exec('UPDATE tb_broadcasts SET cursor_user_id = ?, enqueued = enqueued + ? WHERE id = ?', [$last, $n, $b['id']]);
            }
            return $n;
        });
    }

    public static function cleanup(): int
    {
        $db = App::db();
        $n = 0;
        $n += $db->exec('DELETE FROM tb_processed_updates WHERE processed_at < UTC_TIMESTAMP() - INTERVAL 3 DAY LIMIT 5000');
        $n += $db->exec('DELETE FROM tb_failed_updates WHERE updated_at < UTC_TIMESTAMP() - INTERVAL 3 DAY LIMIT 5000');
        $n += $db->exec('DELETE FROM tb_seen WHERE seen_at < UTC_TIMESTAMP() - INTERVAL 2 DAY LIMIT 5000');
        $n += $db->exec("DELETE FROM tb_outbox WHERE status IN ('sent','failed') AND updated_at < UTC_TIMESTAMP() - INTERVAL 3 DAY LIMIT 5000");
        // Juda eski yuborilmagan xabarlar (masalan suhbat matni) uzoq saqlanmaydi
        $n += $db->exec("UPDATE tb_outbox SET status = 'failed', payload = '{}', last_error = 'expired' WHERE status IN ('pending','sending') AND created_at < UTC_TIMESTAMP() - INTERVAL 2 DAY LIMIT 5000");
        $n += $db->exec('DELETE FROM tb_reg_msgs WHERE created_at < UTC_TIMESTAMP() - INTERVAL 3 DAY LIMIT 5000');
        $n += $db->exec('DELETE FROM tb_notices WHERE sent_at < UTC_TIMESTAMP() - INTERVAL 40 DAY LIMIT 5000');
        $n += $db->exec('DELETE FROM tb_daily_limits WHERE day < UTC_DATE() - INTERVAL 3 DAY LIMIT 5000');
        $n += $db->exec("DELETE FROM tb_settings WHERE name LIKE 'menu\\_draft:%' AND updated_at < UTC_TIMESTAMP() - INTERVAL 7 DAY");
        return $n;
    }
}
