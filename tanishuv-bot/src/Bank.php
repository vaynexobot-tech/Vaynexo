<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * SMS/bank kirimlari. Telegram Stars dan butunlay alohida hisob.
 * Bank kirimi HECH QACHON Premium yoki boostni yoqmaydi.
 * To‘liq karta raqami, PIN, CVV saqlanmaydi: faqat nom va oxirgi 4 raqam.
 */
final class Bank
{
    public const MAX_BODY = 32768;

    public static function sign(string $secret, string $ts, string $raw): string
    {
        return hash_hmac('sha256', $ts . '.' . $raw, $secret);
    }

    /** @return array{0:int,1:array} HTTP kod va JSON javob */
    public static function handle(string $raw, ?string $ts, ?string $sig): array
    {
        if (!App::cfg('bank.enabled')) {
            return [503, ['ok' => false, 'error' => 'disabled']];
        }
        $secret = (string)App::cfg('bank.hmac_secret', '');
        if (strlen($secret) < 32) {
            return [503, ['ok' => false, 'error' => 'not_configured']];
        }
        if (strlen($raw) > self::MAX_BODY) {
            return [413, ['ok' => false, 'error' => 'body_too_large']];
        }
        $ts = trim((string)$ts);
        if (!preg_match('/^\d{9,11}$/', $ts)) {
            return [401, ['ok' => false, 'error' => 'bad_timestamp']];
        }
        if (abs(time() - (int)$ts) > (int)App::cfg('bank.max_skew', 300)) {
            return [401, ['ok' => false, 'error' => 'timestamp_skew']];
        }
        $sig = strtolower(trim((string)$sig));
        if (str_starts_with($sig, 'sha256=')) {
            $sig = substr($sig, 7);
        }
        if (!preg_match('/^[0-9a-f]{64}$/', $sig) || !hash_equals(self::sign($secret, $ts, $raw), $sig)) {
            return [401, ['ok' => false, 'error' => 'bad_signature']];
        }
        $j = json_decode($raw, true);
        if (!is_array($j) || array_is_list($j)) {
            return [400, ['ok' => false, 'error' => 'invalid_json']];
        }
        $e = self::validate($j);
        if (is_string($e)) {
            return [422, ['ok' => false, 'error' => 'invalid_field', 'field' => $e]];
        }
        if ($e['test']) {
            // Test: faqat imzo va format tekshiriladi. DB ga yozilmaydi, pending yopilmaydi, "Ulangan" yoqilmaydi.
            return [200, ['ok' => true, 'test' => true, 'valid' => true]];
        }
        return self::record($e);
    }

    /** @return array|string normallashgan event yoki xato maydon nomi */
    public static function validate(array $j): array|string
    {
        $src = $j['source'] ?? null;
        if (!is_string($src) || !preg_match('/^[A-Za-z0-9_.-]{1,64}$/', $src)) {
            return 'source';
        }
        $eid = $j['event_id'] ?? null;
        if (!is_string($eid) || !preg_match('/^[A-Za-z0-9_.:-]{1,128}$/', $eid)) {
            return 'event_id';
        }
        $test = $j['test'] ?? false;
        if (!is_bool($test)) {
            return 'test';
        }
        $amt = $j['amount_minor'] ?? null;
        if (!is_int($amt) || $amt <= 0 || $amt > 1000000000000000) {
            return 'amount_minor';
        }
        $cur = $j['currency'] ?? null;
        if (!is_string($cur) || !preg_match('/^[A-Z]{3}$/', $cur)) {
            return 'currency';
        }
        $last4 = $j['card_last4'] ?? null;
        if ($last4 !== null && (!is_string($last4) || !preg_match('/^\d{4}$/', $last4))) {
            return 'card_last4';
        }
        $ref = $j['reference'] ?? null;
        if ($ref !== null && (!is_string($ref) || !preg_match('/^[A-Za-z0-9_-]{1,64}$/', $ref))) {
            return 'reference';
        }
        $occ = $j['occurred_at'] ?? null;
        $occAt = null;
        if ($occ !== null) {
            if (!is_string($occ) || ($t = strtotime($occ)) === false) {
                return 'occurred_at';
            }
            $occAt = gmdate('Y-m-d H:i:s', $t);
        }
        return ['source' => $src, 'event_id' => $eid, 'test' => $test, 'amount' => $amt, 'currency' => $cur, 'last4' => $last4, 'ref' => $ref, 'occurred' => $occAt];
    }

    private static function record(array $e): array
    {
        $db = App::db();
        try {
            return $db->tx(static function (Db $db) use ($e): array {
                $dup = $db->one('SELECT id, result, pending_id FROM tb_bank_events WHERE source = ? AND event_id = ? FOR UPDATE', [$e['source'], $e['event_id']]);
                if ($dup) {
                    return [200, ['ok' => true, 'duplicate' => true, 'result' => $dup['result']]];
                }
                if ($e['ref'] !== null) {
                    $ids = $db->all(
                        "SELECT id FROM tb_bank_pending WHERE reference = ? AND status = 'pending' AND expires_at > UTC_TIMESTAMP() AND amount_minor = ? AND currency = ? FOR UPDATE",
                        [$e['ref'], $e['amount'], $e['currency']]
                    );
                } elseif ($e['last4'] !== null) {
                    $ids = $db->all(
                        "SELECT p.id FROM tb_bank_pending p JOIN tb_cards c ON c.id = p.card_id
                         WHERE c.last4 = ? AND p.status = 'pending' AND p.expires_at > UTC_TIMESTAMP() AND p.amount_minor = ? AND p.currency = ? FOR UPDATE",
                        [$e['last4'], $e['amount'], $e['currency']]
                    );
                } else {
                    $ids = [];
                }
                $count = count($ids);
                $result = $count === 1 ? 'matched' : ($count === 0 ? 'unmatched' : 'ambiguous');
                $pid = $count === 1 ? (int)$ids[0]['id'] : null;
                $db->exec(
                    'INSERT INTO tb_bank_events (source, event_id, amount_minor, currency, card_last4, reference, occurred_at, received_at, result, pending_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, UTC_TIMESTAMP(), ?, ?)',
                    [$e['source'], $e['event_id'], $e['amount'], $e['currency'], $e['last4'], $e['ref'], $e['occurred'], $result, $pid]
                );
                $evId = $db->lastId();
                if ($pid !== null) {
                    $db->exec("UPDATE tb_bank_pending SET status = 'matched', matched_event_id = ? WHERE id = ? AND status = 'pending'", [$evId, $pid]);
                }
                $db->setSetting('bank_connected_at', gmdate('Y-m-d H:i:s'));
                foreach ((array)App::cfg('admin_ids', []) as $aid) {
                    $aid = (int)$aid;
                    if ($aid > 0) {
                        $al = Lang::norm(Users::find($aid)['lang'] ?? null);
                        Outbox::add($aid, 'sendMessage', ['chat_id' => $aid, 'text' => Lang::t($al, 'adm.bank_event', [
                            'result' => $result, 'amount' => $e['amount'], 'currency' => $e['currency'], 'id' => $evId,
                        ])], 'bank:' . $evId . ':' . $aid);
                    }
                }
                return [200, ['ok' => true, 'result' => $result, 'pending_id' => $pid]];
            });
        } catch (\Throwable $ex) {
            if (Db::isDuplicate($ex)) {
                return [200, ['ok' => true, 'duplicate' => true]];
            }
            throw $ex;
        }
    }

    public static function createPending(int $userId, int $cardId, int $amount, string $currency, ?string $ref, int $hours = 24): int
    {
        $db = App::db();
        $db->exec(
            "INSERT INTO tb_bank_pending (user_id, card_id, amount_minor, currency, reference, status, created_at, expires_at)
             VALUES (?, ?, ?, ?, ?, 'pending', UTC_TIMESTAMP(), UTC_TIMESTAMP() + INTERVAL ? HOUR)",
            [$userId, $cardId, $amount, $currency, $ref, max(1, min(720, $hours))]
        );
        return $db->lastId();
    }

    public static function addCard(string $title, string $last4): int
    {
        App::db()->exec('INSERT INTO tb_cards (title, last4, active, created_at) VALUES (?, ?, 1, UTC_TIMESTAMP())', [$title, $last4]);
        return App::db()->lastId();
    }

    // ---------------- Admin bo‘limi ----------------

    public static function adminCallback(Ctx $ctx, array $p): void
    {
        $a = $p[1];
        $arg = $p[2] ?? '';
        $db = App::db();
        $back = [[$ctx->t('btn.back'), 'a:bk']];
        switch ($a) {
            case 'bk':
                $ctx->edit($ctx->t('adm.bank_title'), Kb::inline([
                    [[$ctx->t('adm.bank_status'), 'a:bks'], [$ctx->t('adm.bank_cards'), 'a:bkc:0']],
                    [[$ctx->t('adm.bank_pending'), 'a:bkp'], [$ctx->t('adm.bank_history'), 'a:bkh']],
                    [[$ctx->t('adm.bank_stars'), 'a:bkt']],
                    [[$ctx->t('btn.back'), 'a:h']],
                ]));
                return;
            case 'bks':
                $conn = $db->setting('bank_connected_at');
                $ctx->send($ctx->t('adm.bank_status_text', [
                    'enabled' => App::cfg('bank.enabled') ? '✅' : '⛔',
                    'conn' => $conn ? $ctx->t('adm.bank_connected', ['date' => $conn . ' UTC']) : $ctx->t('adm.bank_not_connected'),
                    'url' => rtrim((string)App::cfg('public_url'), '/') . '/bank-webhook.php',
                ]), Kb::inline([$back]));
                return;
            case 'bkc':
                $page = max(0, (int)$arg);
                $per = 30;
                $off = $page * $per;
                $total = (int)$db->val('SELECT COUNT(*) FROM tb_cards');
                $rows = $db->all("SELECT * FROM tb_cards ORDER BY id ASC LIMIT $per OFFSET $off");
                $kb = [];
                foreach ($rows as $c) {
                    $kb[] = [[($c['active'] ? '✅ ' : '⛔ ') . mb_substr($c['title'], 0, 24) . ' **** ' . $c['last4'], 'a:bkd:' . $c['id']]];
                }
                $nav = [];
                if ($page > 0) {
                    $nav[] = ['⬅️', 'a:bkc:' . ($page - 1)];
                }
                if ($off + $per < $total) {
                    $nav[] = ['➡️', 'a:bkc:' . ($page + 1)];
                }
                if ($nav) {
                    $kb[] = $nav;
                }
                $kb[] = [[$ctx->t('adm.card_add'), 'a:bka']];
                $kb[] = $back;
                $ctx->send($ctx->t('adm.cards_title', ['n' => $total]), Kb::inline($kb));
                return;
            case 'bka':
                $ctx->setState('adm:card', ['step' => 'title']);
                $ctx->send($ctx->t('adm.card_title_prompt'), Kb::inline([$back]));
                return;
            case 'bkd':
                $n = $db->exec('UPDATE tb_cards SET active = 1 - active WHERE id = ?', [(int)$arg]);
                if ($n) {
                    Admin::audit($ctx, 'card.toggle', (string)(int)$arg);
                }
                self::adminCallback($ctx, ['a', 'bkc', '0']);
                return;
            case 'bkp':
                $rows = $db->all("SELECT p.*, c.last4 FROM tb_bank_pending p LEFT JOIN tb_cards c ON c.id = p.card_id WHERE p.status = 'pending' ORDER BY p.id DESC LIMIT 20");
                $lines = [$ctx->t('adm.pending_title', ['n' => count($rows)])];
                foreach ($rows as $r) {
                    $lines[] = '#' . $r['id'] . ' · user ' . $r['user_id'] . ' · **** ' . ($r['last4'] ?? '?') . ' · ' . $r['amount_minor'] . ' ' . $r['currency']
                        . ($r['reference'] ? ' · ' . $r['reference'] : '') . ' · ' . substr((string)$r['expires_at'], 0, 16);
                }
                $ctx->send(implode("\n", $lines), Kb::inline([[[$ctx->t('adm.pending_add'), 'a:bkn']], $back]));
                return;
            case 'bkn':
                $ctx->setState('adm:pend');
                $ctx->send($ctx->t('adm.pending_prompt'), Kb::inline([$back]));
                return;
            case 'bkh':
                $rows = $db->all('SELECT * FROM tb_bank_events ORDER BY id DESC LIMIT 20');
                $lines = [$ctx->t('adm.history_title')];
                foreach ($rows as $r) {
                    $lines[] = '#' . $r['id'] . ' · ' . $r['result'] . ' · ' . $r['amount_minor'] . ' ' . $r['currency'] . ' · ' . $r['source'] . ' · ' . substr((string)$r['received_at'], 0, 16);
                }
                $ctx->send(implode("\n", $lines), Kb::inline([$back]));
                return;
            case 'bkt':
                $sum = (int)$db->val("SELECT COALESCE(SUM(amount),0) FROM tb_orders WHERE status = 'paid' AND currency = 'XTR'");
                $cnt = (int)$db->val("SELECT COUNT(*) FROM tb_orders WHERE status = 'paid'");
                $rej = (int)$db->val('SELECT COUNT(*) FROM tb_rejected_payments');
                $rows = $db->all("SELECT id, user_id, kind, days, amount, paid_at FROM tb_orders WHERE status = 'paid' ORDER BY paid_at DESC LIMIT 10");
                $lines = [$ctx->t('adm.stars_title', ['sum' => $sum, 'n' => $cnt, 'rej' => $rej])];
                foreach ($rows as $r) {
                    $lines[] = substr((string)$r['paid_at'], 0, 16) . ' · ' . $r['user_id'] . ' · ' . $r['kind'] . ' ' . $r['days'] . 'd · ' . $r['amount'] . ' XTR';
                }
                $ctx->send(implode("\n", $lines), Kb::inline([$back]));
                return;
        }
        $ctx->send($ctx->t('err.stale'));
    }

    public static function adminInput(Ctx $ctx, string $text): void
    {
        $state = (string)$ctx->u['state'];
        $d = $ctx->stateData();
        if ($state === 'adm:card') {
            if (($d['step'] ?? 'title') === 'title') {
                $title = Users::validName($text);
                if ($title === null || mb_strlen($text) > 64) {
                    $ctx->send($ctx->t('adm.card_title_bad'));
                    return;
                }
                $ctx->setState('adm:card', ['step' => 'last4', 'title' => $title]);
                $ctx->send($ctx->t('adm.card_last4_prompt'));
                return;
            }
            $digits = preg_replace('/\D/', '', $text);
            if (strlen((string)$digits) !== 4) {
                // To‘liq raqam yuborilsa ham saqlanmaydi
                $ctx->send($ctx->t('adm.card_only4'));
                return;
            }
            $id = self::addCard((string)$d['title'], (string)$digits);
            Admin::audit($ctx, 'card.add', (string)$id, '**** ' . $digits);
            $ctx->setState(null);
            $ctx->send($ctx->t('adm.card_added', ['title' => $d['title'], 'last4' => $digits]));
            self::adminCallback($ctx, ['a', 'bkc', '0']);
            return;
        }
        if ($state === 'adm:pend') {
            $parts = preg_split('/\s+/', trim($text));
            if (count($parts) < 4 || !ctype_digit($parts[0]) || !ctype_digit($parts[1]) || !ctype_digit($parts[2]) || !preg_match('/^[A-Z]{3}$/', $parts[3])
                || (isset($parts[4]) && !preg_match('/^[A-Za-z0-9_-]{1,64}$/', $parts[4]))) {
                $ctx->send($ctx->t('adm.pending_bad'));
                return;
            }
            $card = App::db()->one('SELECT id FROM tb_cards WHERE id = ? AND active = 1', [(int)$parts[1]]);
            if (!$card) {
                $ctx->send($ctx->t('adm.not_found'));
                return;
            }
            $id = self::createPending((int)$parts[0], (int)$parts[1], (int)$parts[2], $parts[3], $parts[4] ?? null);
            Admin::audit($ctx, 'bank.pending_add', (string)$id);
            $ctx->setState(null);
            $ctx->send($ctx->t('adm.pending_added', ['id' => $id]));
            return;
        }
        $ctx->setState(null);
    }
}
