<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

final class Bot
{
    /**
     * Update ni qayta ishlaydi. Update marker va barcha biznes o‘zgarishlar bitta tranzaksiyada.
     * Xato bo‘lsa hammasi rollback qilinadi va istisno tashqariga chiqadi (webhook 500 qaytaradi,
     * Telegram ayni update ni qayta yuboradi).
     * @return array{status:string, out:int[]}
     */
    public static function handleUpdate(array $upd): array
    {
        $updateId = $upd['update_id'] ?? null;
        if (!is_int($updateId) || $updateId < 0) {
            return ['status' => 'bad', 'out' => []];
        }
        if (isset($upd['pre_checkout_query'])) {
            return Payments::preCheckout($updateId, (array)$upd['pre_checkout_query']);
        }

        $msg = isset($upd['message']) && is_array($upd['message']) ? $upd['message'] : null;
        $cb = isset($upd['callback_query']) && is_array($upd['callback_query']) ? $upd['callback_query'] : null;
        $uid = self::validSender($msg, $cb);

        $db = App::db();
        for ($attempt = 0; ; $attempt++) {
            $db->begin();
            try {
                $n = $db->exec('INSERT IGNORE INTO tb_processed_updates (update_id, processed_at) VALUES (?, UTC_TIMESTAMP())', [$updateId]);
                if ($n === 0) {
                    $db->commit();
                    return ['status' => 'duplicate', 'out' => []];
                }
                if ($uid === null) {
                    $db->commit();
                    return ['status' => 'ignored', 'out' => []];
                }
                $ctx = new Ctx($uid, $updateId, $msg, $cb);
                if ($msg !== null) {
                    RegCleanup::incoming($ctx);
                }
                App::hook('after_user_lock');
                if ($cb) {
                    Router::callback($ctx, (string)($cb['data'] ?? ''));
                } else {
                    Router::message($ctx, $msg);
                }
                $ctx->finish();
                App::hook('before_commit');
                $db->commit();
                return ['status' => 'ok', 'out' => $ctx->out];
            } catch (\Throwable $e) {
                $db->rollBack();
                if ($attempt < 3 && Db::isRetryable($e)) {
                    usleep(30000 * ($attempt + 1));
                    continue;
                }
                if (self::giveUp($updateId, $e)) {
                    return ['status' => 'gave_up', 'out' => []];
                }
                throw $e;
            }
        }
    }

    public const MAX_FAILURES = 5;

    /**
     * Xato bergan update ni sanaydi. Telegram uni qayta yuboradi; lekin bir xil update
     * MAX_FAILURES marta yiqilsa, bot boshqa update larni kutib qolmasligi uchun
     * u qayd etiladi va 200 qaytariladi (xato logga yoziladi).
     */
    private static function giveUp(int $updateId, \Throwable $e): bool
    {
        try {
            $db = App::db();
            $db->exec(
                'INSERT INTO tb_failed_updates (update_id, attempts, last_error, updated_at) VALUES (?, 1, ?, UTC_TIMESTAMP())
                 ON DUPLICATE KEY UPDATE attempts = attempts + 1, last_error = VALUES(last_error), updated_at = VALUES(updated_at)',
                [$updateId, mb_substr(Log::scrub(get_class($e) . ': ' . $e->getMessage()), 0, 250)]
            );
            $n = (int)$db->val('SELECT attempts FROM tb_failed_updates WHERE update_id = ?', [$updateId]);
            if ($n >= self::MAX_FAILURES) {
                $db->exec('INSERT IGNORE INTO tb_processed_updates (update_id, processed_at) VALUES (?, UTC_TIMESTAMP())', [$updateId]);
                Log::error('update ' . $updateId . ' ' . $n . ' marta yiqildi, o‘tkazib yuborildi', $e);
                return true;
            }
        } catch (\Throwable $ignored) {
        }
        return false;
    }

    /** Faqat private chat, chat.id == from.id, bot emas. */
    private static function validSender(?array $msg, ?array $cb): ?int
    {
        if ($msg) {
            $from = $msg['from'] ?? null;
            $chat = $msg['chat'] ?? null;
        } elseif ($cb) {
            $from = $cb['from'] ?? null;
            $chat = $cb['message']['chat'] ?? null;
        } else {
            return null;
        }
        if (!is_array($from) || !is_array($chat) || !empty($from['is_bot'])) {
            return null;
        }
        if (($chat['type'] ?? '') !== 'private') {
            return null;
        }
        if (!is_int($from['id'] ?? null) || !is_int($chat['id'] ?? null) || $from['id'] !== $chat['id'] || $from['id'] <= 0) {
            return null;
        }
        return $from['id'];
    }
}
