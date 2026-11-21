<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Telegramga chiquvchi barcha xabarlar shu navbat orqali yuboriladi.
 * dedupe_key UNIQUE: bir xil xabar ikki marta navbatga tushmaydi.
 * Yuborilgan yoki uzil-kesil rad etilgan xabar payload i '{}' bilan tozalanadi.
 */
final class Outbox
{
    public const MAX_ATTEMPTS = 8;

    public static function add(int $chatId, string $method, array $params, string $dedupe, int $priority = 5): ?int
    {
        $db = App::db();
        $n = $db->exec(
            'INSERT IGNORE INTO tb_outbox (dedupe_key, chat_id, method, payload, priority, status, attempts, next_attempt_at, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, \'pending\', 0, UTC_TIMESTAMP(), UTC_TIMESTAMP(), UTC_TIMESTAMP())',
            [substr($dedupe, 0, 120), $chatId, $method, json_encode($params, JSON_UNESCAPED_UNICODE), $priority]
        );
        return $n > 0 ? $db->lastId() : null;
    }

    /** Navbatdagi xabarlarni yuboradi. $ids berilsa faqat o‘shalarni. Yuborilganlar sonini qaytaradi. */
    public static function process(float $deadline, int $max = 500, ?array $ids = null): int
    {
        $db = App::db();
        $sent = 0;
        while ($sent < $max && microtime(true) < $deadline) {
            $token = bin2hex(random_bytes(8));
            $sql = "UPDATE tb_outbox SET status = 'sending', claim_token = ?, locked_until = UTC_TIMESTAMP() + INTERVAL 60 SECOND, updated_at = UTC_TIMESTAMP()
                    WHERE ((status = 'pending' AND next_attempt_at <= UTC_TIMESTAMP()) OR (status = 'sending' AND locked_until < UTC_TIMESTAMP()))";
            $p = [$token];
            if ($ids !== null) {
                $ids = array_values(array_filter(array_map('intval', $ids)));
                if (!$ids) {
                    return $sent;
                }
                $sql .= ' AND id IN (' . implode(',', array_fill(0, count($ids), '?')) . ')';
                $p = array_merge($p, $ids);
            }
            $sql .= ' ORDER BY priority ASC, id ASC LIMIT 20';
            if ($db->exec($sql, $p) === 0) {
                break;
            }
            $rows = $db->all('SELECT * FROM tb_outbox WHERE claim_token = ? ORDER BY priority ASC, id ASC', [$token]);
            $stop = false;
            foreach ($rows as $row) {
                if ($stop || microtime(true) >= $deadline) {
                    $db->exec("UPDATE tb_outbox SET status = 'pending', claim_token = NULL, locked_until = NULL WHERE id = ? AND claim_token = ?", [$row['id'], $token]);
                    continue;
                }
                $r = self::deliver($row);
                if ($r === 'sent') {
                    $sent++;
                } elseif ($r === 'flood') {
                    $stop = true;
                }
            }
            if ($stop) {
                break;
            }
        }
        return $sent;
    }

    private static function deliver(array $row): string
    {
        $db = App::db();
        $params = json_decode((string)$row['payload'], true);
        if (!is_array($params) || $params === []) {
            $db->exec("UPDATE tb_outbox SET status='failed', payload='{}', claim_token=NULL, last_error='empty payload', updated_at=UTC_TIMESTAMP() WHERE id=?", [$row['id']]);
            return 'failed';
        }
        $track = !empty($params[RegCleanup::KEY]);
        unset($params[RegCleanup::KEY]);
        $res = App::tg()->call((string)$row['method'], $params);
        if (!empty($res['ok'])) {
            $db->exec("UPDATE tb_outbox SET status='sent', payload='{}', claim_token=NULL, locked_until=NULL, last_error=NULL, updated_at=UTC_TIMESTAMP() WHERE id=?", [$row['id']]);
            if ($track) {
                try {
                    RegCleanup::sent((int)$row['chat_id'], $res['result'] ?? null);
                } catch (\Throwable $e) {
                    Log::error('reg cleanup track', $e);
                }
            }
            return 'sent';
        }
        $code = (int)($res['error_code'] ?? 0);
        $desc = mb_substr(Log::scrub((string)($res['description'] ?? '')), 0, 250);
        $attempts = (int)$row['attempts'] + 1;

        if ($code === 429) {
            $retry = max(1, min(3600, (int)($res['parameters']['retry_after'] ?? 5)));
            $db->exec(
                "UPDATE tb_outbox SET status='pending', attempts=?, next_attempt_at=UTC_TIMESTAMP() + INTERVAL ? SECOND, claim_token=NULL, locked_until=NULL, last_error=?, updated_at=UTC_TIMESTAMP() WHERE id=?",
                [min($attempts, 60000), $retry, $desc, $row['id']]
            );
            return 'flood';
        }
        if ($code === 400 && stripos($desc, 'message is not modified') !== false) {
            $db->exec("UPDATE tb_outbox SET status='sent', payload='{}', claim_token=NULL, locked_until=NULL, updated_at=UTC_TIMESTAMP() WHERE id=?", [$row['id']]);
            return 'sent';
        }
        if (in_array($code, [400, 401, 403, 404], true)) {
            $db->exec("UPDATE tb_outbox SET status='failed', payload='{}', attempts=?, claim_token=NULL, locked_until=NULL, last_error=?, updated_at=UTC_TIMESTAMP() WHERE id=?", [$attempts, $desc, $row['id']]);
            if ($code === 403) {
                $db->exec('UPDATE tb_users SET blocked_bot = 1 WHERE id = ?', [$row['chat_id']]);
            }
            return 'failed';
        }
        // Vaqtinchalik xato: eksponensial backoff
        if ($attempts >= self::MAX_ATTEMPTS) {
            $db->exec("UPDATE tb_outbox SET status='failed', payload='{}', attempts=?, claim_token=NULL, locked_until=NULL, last_error=?, updated_at=UTC_TIMESTAMP() WHERE id=?", [$attempts, $desc, $row['id']]);
            return 'failed';
        }
        $delay = min(900, 5 * (2 ** $attempts));
        $db->exec(
            "UPDATE tb_outbox SET status='pending', attempts=?, next_attempt_at=UTC_TIMESTAMP() + INTERVAL ? SECOND, claim_token=NULL, locked_until=NULL, last_error=?, updated_at=UTC_TIMESTAMP() WHERE id=?",
            [$attempts, $delay, $desc, $row['id']]
        );
        return 'retry';
    }
}
