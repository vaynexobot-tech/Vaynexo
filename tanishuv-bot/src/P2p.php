<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * P2P to‘lov (Uzcard / Humo): foydalanuvchi bot ko‘rsatgan kartaga ANIQ summani o‘tkazadi,
 * bank SMS i telefon (SMS forwarder) orqali sms-webhook.php ga keladi, summa va karta mos kelsa
 * Premium avtomatik yoqiladi.
 *
 * Moslash: har buyurtmaga noyob summa beriladi (narx + 1..99 so‘m), shuning uchun summa buyurtmani
 * aniq belgilaydi. Noaniq (ambiguous) yoki mos kelmagan kirimga hech qachon Premium berilmaydi.
 * Buyurtma bank_pending.reference da "prem:<product_id>" ko‘rinishida saqlanadi.
 */
final class P2p
{
    public const TTL_HOURS = 1;
    public const MAX_BODY = 16384;

    public static function enabled(): bool
    {
        return Settings::on('p2p_enabled') && self::cardDigits() !== '';
    }

    public static function cardDigits(): string
    {
        $d = preg_replace('/\D/', '', Settings::get('p2p_card'));
        return strlen((string)$d) === 16 ? (string)$d : '';
    }

    public static function prices(): array
    {
        $j = json_decode(Settings::get('p2p_prices'), true);
        $out = [];
        foreach (is_array($j) ? $j : [] as $k => $v) {
            if (is_string($k) && is_int($v) && $v >= 1000 && $v <= 100000000) {
                $out[$k] = $v;
            }
        }
        return $out;
    }

    public static function fmt(int $n): string
    {
        return number_format($n, 0, '', ' ');
    }

    // ---------------- Foydalanuvchi oqimi ----------------

    public static function callback(Ctx $ctx, array $p): void
    {
        if (!self::enabled()) {
            $ctx->answer($ctx->t('err.stale'));
            return;
        }
        $db = App::db();
        $prices = self::prices();
        if (($p[1] ?? '') === 'card') {
            $rows = [];
            foreach (Payments::products('premium') as $prod) {
                if (isset($prices[$prod['code']])) {
                    $rows[] = [[$ctx->t('p2p.pkg', ['days' => $prod['days'], 'price' => self::fmt($prices[$prod['code']])]), 'pm:cb:' . $prod['id']]];
                }
            }
            $rows[] = [[$ctx->t('btn.back'), 'pm:menu']];
            $ctx->answer();
            $ctx->edit($ctx->t('p2p.choose'), Kb::inline($rows));
            return;
        }
        if (($p[1] ?? '') === 'cb' && ctype_digit($p[2] ?? '')) {
            $prod = $db->one("SELECT * FROM tb_products WHERE id = ? AND kind = 'premium' AND active = 1", [(int)$p[2]]);
            if (!$prod || !isset($prices[$prod['code']])) {
                $ctx->answer($ctx->t('err.stale'));
                return;
            }
            $ctx->answer();
            self::start($ctx, $prod, $prices[$prod['code']]);
            return;
        }
        $ctx->answer($ctx->t('err.stale'));
    }

    public static function start(Ctx $ctx, array $prod, int $price): ?int
    {
        $db = App::db();
        $card = self::cardDigits();
        $last4 = substr($card, -4);
        $cardId = (int)$db->val('SELECT id FROM tb_cards WHERE last4 = ? AND active = 1 ORDER BY id LIMIT 1', [$last4]);
        if ($cardId === 0) {
            $cardId = Bank::addCard('P2P', $last4);
        }
        // oldingi ochiq P2P buyurtmani bekor qilamiz (bitta foydalanuvchida bitta ochiq buyurtma)
        $db->exec("UPDATE tb_bank_pending SET status = 'cancelled' WHERE user_id = ? AND status = 'pending' AND reference LIKE 'prem:%'", [$ctx->uid]);
        $offsets = range(1, 99);
        shuffle($offsets);
        $amount = null;
        foreach ($offsets as $off) {
            $minor = ($price + $off) * 100;
            $busy = $db->val(
                "SELECT 1 FROM tb_bank_pending WHERE card_id = ? AND amount_minor = ? AND currency = 'UZS' AND status = 'pending' AND expires_at > UTC_TIMESTAMP() LIMIT 1",
                [$cardId, $minor]
            );
            if ($busy === null) {
                $amount = $minor;
                break;
            }
        }
        if ($amount === null) {
            $ctx->send($ctx->t('p2p.busy'));
            return null;
        }
        $pid = Bank::createPending($ctx->uid, $cardId, $amount, 'UZS', 'prem:' . $prod['id'], self::TTL_HOURS);
        $holder = trim(Settings::get('p2p_holder'));
        $ctx->send($ctx->t('p2p.pay', [
            'amount' => self::fmt(intdiv($amount, 100)),
            'card' => trim(chunk_split($card, 4, ' ')),
            'holder' => $holder !== '' ? $holder : '—',
            'days' => $prod['days'],
            'min' => self::TTL_HOURS * 60,
        ]), Kb::inline([[[$ctx->t('btn.back'), 'pm:menu']]]));
        return $pid;
    }

    /** Bank::record ichida (tranzaksiyada) mos kelgan pending uchun chaqiriladi. Idempotent: pending faqat bir marta matched bo‘ladi. */
    public static function onMatched(Db $db, int $pendingId): void
    {
        $p = $db->one('SELECT * FROM tb_bank_pending WHERE id = ?', [$pendingId]);
        if (!$p || !preg_match('/^prem:(\d{1,9})$/', (string)$p['reference'], $m)) {
            return;
        }
        $prod = $db->one("SELECT * FROM tb_products WHERE id = ? AND kind = 'premium'", [(int)$m[1]]);
        $u = Users::find((int)$p['user_id'], true);
        if (!$prod || !$u) {
            return;
        }
        $days = (int)$prod['days'];
        $db->exec(
            "UPDATE tb_users SET premium_until = GREATEST(COALESCE(premium_until, UTC_TIMESTAMP()), UTC_TIMESTAMP()) + INTERVAL $days DAY WHERE id = ?",
            [$u['id']]
        );
        $db->exec(
            "INSERT INTO tb_orders (id, user_id, product_id, kind, audience, days, amount, currency, status, created_at, expires_at, paid_at)
             VALUES (?, ?, ?, 'premium', NULL, ?, ?, 'UZS', 'paid', UTC_TIMESTAMP(), UTC_TIMESTAMP(), UTC_TIMESTAMP())",
            [bin2hex(random_bytes(16)), $u['id'], $prod['id'], $days, intdiv((int)$p['amount_minor'], 100)]
        );
        $l = Lang::norm($u['lang'] ?? null);
        Outbox::add((int)$u['id'], 'sendMessage', ['chat_id' => (int)$u['id'], 'text' => Lang::t($l, 'p2p.paid', ['days' => $days])], 'p2p:' . $pendingId, 1);
    }

    // ---------------- SMS ----------------

    /** @return array{amount_minor:int,last4:?string}|null  Faqat kirim (hisobga tushish) SMS lari. */
    public static function parseSms(string $text): ?array
    {
        $t = trim(preg_replace('/\s+/u', ' ', $text) ?? '');
        if ($t === '' || mb_strlen($t) > 1000) {
            return null;
        }
        $low = mb_strtolower($t);
        $credit = ['popolnenie', 'пополнение', 'kirim', 'qabul', 'zachislen', 'зачислен', 'o‘tkazma', "o'tkazma", 'perevod', 'перевод', 'credit', 'received', 'hisobga tushdi', 'tushdi', 'поступление', 'postuplenie'];
        $debit = ['spisanie', 'списание', 'oplata', 'оплата', 'pokupka', 'покупка', 'to‘lov', "to'lov", 'chiqim', 'snyatie', 'снятие', 'purchase', 'withdraw', 'debit'];
        $hasPlus = (bool)preg_match('/(?<![\w])\+\s?\d/u', $t);
        $hasCredit = $hasPlus;
        foreach ($credit as $w) {
            if (str_contains($low, $w)) {
                $hasCredit = true;
            }
        }
        $hasDebit = false;
        foreach ($debit as $w) {
            if (str_contains($low, $w)) {
                $hasDebit = true;
            }
        }
        if (!$hasCredit || ($hasDebit && !$hasPlus)) {
            return null;
        }
        $num = '(\d{1,3}(?:[ ,\x{00A0}]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)';
        if (!preg_match_all('/(\+\s?)?' . $num . '\s*(?:UZS|SUM|so[\'‘’`ʻ]?m|сум)/iu', $t, $mm, PREG_SET_ORDER | PREG_OFFSET_CAPTURE)) {
            return null;
        }
        $pick = null;
        foreach ($mm as $m) {
            if ($m[1][0] !== '') {
                $pick = $m;
                break;
            }
        }
        if ($pick === null) {
            foreach ($mm as $m) {
                $before = mb_strtolower(substr($t, max(0, $m[0][1] - 25), min(25, $m[0][1])));
                if (preg_match('/(balans|balance|dostupno|ostatok|qoldiq|доступно|баланс|остаток)/u', $before)) {
                    continue;
                }
                $pick = $m;
                break;
            }
        }
        if ($pick === null) {
            return null;
        }
        $minor = self::toMinor($pick[2][0]);
        if ($minor === null || $minor <= 0) {
            return null;
        }
        $last4 = null;
        if (preg_match('/(?:\*+|•+|\bkarta\b|\bcard\b|карт[аы])[^\d]{0,12}(\d{4})(?!\d)/iu', $t, $c)) {
            $last4 = $c[1];
        }
        return ['amount_minor' => $minor, 'last4' => $last4];
    }

    private static function toMinor(string $s): ?int
    {
        $s = str_replace(["\u{00A0}", ' '], '', $s);
        $hasC = str_contains($s, ',');
        $hasD = str_contains($s, '.');
        if ($hasC && $hasD) {
            $dec = strrpos($s, ',') > strrpos($s, '.') ? ',' : '.';
            $thou = $dec === ',' ? '.' : ',';
            $s = str_replace($thou, '', $s);
            $s = str_replace($dec, '.', $s);
        } elseif ($hasC || $hasD) {
            $sep = $hasC ? ',' : '.';
            $parts = explode($sep, $s);
            if (count($parts) > 2 || strlen((string)end($parts)) === 3) {
                $s = implode('', $parts);          // ming ajratuvchi
            } else {
                $s = $parts[0] . '.' . $parts[1];  // o‘nlik
            }
        }
        if (!preg_match('/^\d+(\.\d{1,2})?$/', $s)) {
            return null;
        }
        return (int)round(((float)$s) * 100);
    }

    /** @return array{0:int,1:array} */
    public static function handleSms(string $sender, string $text, ?string $eventId): array
    {
        if (!self::enabled()) {
            return [503, ['ok' => false, 'error' => 'disabled']];
        }
        $allowed = array_filter(array_map(static fn($s) => mb_strtolower(trim($s)), explode(',', Settings::get('p2p_senders'))));
        if ($allowed && !in_array(mb_strtolower(trim($sender)), $allowed, true)) {
            return [200, ['ok' => true, 'ignored' => 'sender']];
        }
        $parsed = self::parseSms($text);
        if ($parsed === null) {
            return [200, ['ok' => true, 'ignored' => 'not_income']];
        }
        $eid = $eventId !== null && preg_match('/^[A-Za-z0-9_.:-]{1,100}$/', $eventId) ? $eventId : sha1($sender . '|' . $text);
        $last4 = $parsed['last4'] ?? substr(self::cardDigits(), -4);
        return Bank::recordEvent([
            'source' => 'sms', 'event_id' => $eid, 'test' => false, 'amount' => $parsed['amount_minor'],
            'currency' => 'UZS', 'last4' => $last4, 'ref' => null, 'occurred' => null,
        ]);
    }

    // ---------------- Admin ----------------

    public static function adminCallback(Ctx $ctx, string $a, string $arg): void
    {
        $back = Kb::inline([[[$ctx->t('btn.back'), 'a:pp']]]);
        switch ($a) {
            case 'pp':
                $cd = self::cardDigits();
                $prices = [];
                foreach (self::prices() as $k => $v) {
                    $prices[] = $k . '=' . self::fmt($v);
                }
                $txt = $ctx->t('adm.p2p_title', [
                    'on' => Settings::on('p2p_enabled') ? '✅' : '❌',
                    'card' => $cd !== '' ? '**** ' . substr($cd, -4) : '—',
                    'holder' => trim(Settings::get('p2p_holder')) ?: '—',
                    'senders' => trim(Settings::get('p2p_senders')) ?: '—',
                    'prices' => $prices ? implode(', ', $prices) : '—',
                    'key' => strlen((string)App::cfg('bank.sms_key', '')) >= 32 ? '✅' : '⛔',
                    'url' => rtrim((string)App::cfg('public_url'), '/') . '/sms-webhook.php',
                ]);
                $ctx->edit($txt, Kb::inline([
                    [[$ctx->t('adm.p2p_toggle'), 'a:ppt']],
                    [[$ctx->t('adm.p2p_card'), 'a:ppc'], [$ctx->t('adm.p2p_senders'), 'a:pps']],
                    [[$ctx->t('adm.p2p_prices'), 'a:ppp']],
                    [[$ctx->t('btn.back'), 'a:cfg']],
                ]));
                return;
            case 'ppt':
                Settings::set('p2p_enabled', Settings::on('p2p_enabled') ? '0' : '1');
                Admin::audit($ctx, 'settings.p2p_enabled', null, Settings::get('p2p_enabled'));
                self::adminCallback($ctx, 'pp', '');
                return;
            case 'ppc':
            case 'pps':
            case 'ppp':
                $ctx->setState('adm:p2p' . substr($a, 2));
                $ctx->send($ctx->t('adm.p2p_prompt_' . substr($a, 2)), $back);
                return;
        }
    }

    public static function adminInput(Ctx $ctx, string $state, string $text): void
    {
        $back = Kb::inline([[[$ctx->t('btn.back'), 'a:pp']]]);
        $text = trim($text);
        if ($state === 'adm:p2pc') {
            [$num, $holder] = array_pad(array_map('trim', explode('|', $text, 2)), 2, '');
            $d = preg_replace('/\D/', '', $num);
            if (strlen((string)$d) !== 16 || mb_strlen($holder) > 60) {
                $ctx->send($ctx->t('adm.p2p_bad_card'), $back);
                return;
            }
            Settings::set('p2p_card', (string)$d);
            Settings::set('p2p_holder', $holder);
            Admin::audit($ctx, 'p2p.card', '**** ' . substr((string)$d, -4));
        } elseif ($state === 'adm:p2ps') {
            $list = array_filter(array_map('trim', explode(',', $text)));
            if ($text === '-') {
                $list = [];
            }
            foreach ($list as $s) {
                if (!preg_match('/^[A-Za-z0-9_+.\- ]{2,30}$/', $s)) {
                    $ctx->send($ctx->t('adm.p2p_bad_senders'), $back);
                    return;
                }
            }
            Settings::set('p2p_senders', implode(',', $list));
            Admin::audit($ctx, 'p2p.senders', null, implode(',', $list));
        } elseif ($state === 'adm:p2pp') {
            $known = [];
            foreach (Payments::products('premium') as $prod) {
                $known[$prod['code']] = true;
            }
            $out = [];
            foreach (preg_split('/[,\n;]+/', $text) ?: [] as $pair) {
                if (!preg_match('/^\s*([a-z0-9_]{1,32})\s*=\s*([\d ]{4,9})\s*$/', $pair, $m) || !isset($known[$m[1]])) {
                    $ctx->send($ctx->t('adm.p2p_bad_prices'), $back);
                    return;
                }
                $v = (int)str_replace(' ', '', $m[2]);
                if ($v < 1000 || $v > 100000000) {
                    $ctx->send($ctx->t('adm.p2p_bad_prices'), $back);
                    return;
                }
                $out[$m[1]] = $v;
            }
            if (!$out) {
                $ctx->send($ctx->t('adm.p2p_bad_prices'), $back);
                return;
            }
            Settings::set('p2p_prices', (string)json_encode($out));
            Admin::audit($ctx, 'p2p.prices', null, (string)json_encode($out));
        } else {
            $ctx->setState(null);
            return;
        }
        $ctx->setState(null);
        self::adminCallback($ctx, 'pp', '');
    }
}
