<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Telegram Stars (XTR) to‘lovlari. Raqamli xizmat FAQAT successful_payment orqali yoqiladi.
 * Avtomatik obuna yo‘q. Admin tasdig‘i talab qilinmaydi.
 */
final class Payments
{
    public const ORDER_TTL_HOURS = 24;

    public static function products(string $kind): array
    {
        return App::db()->all('SELECT * FROM tb_products WHERE kind = ? AND active = 1 ORDER BY sort, id', [$kind]);
    }

    public static function premiumMenu(Ctx $ctx): void
    {
        $u = $ctx->u;
        $caps = Limits::caps($u);
        $used = Limits::used($ctx->uid);
        $lines = [$ctx->t('premium.title')];
        $lines[] = Users::isPremium($u)
            ? $ctx->t('premium.active', ['date' => substr((string)$u['premium_until'], 0, 16) . ' UTC'])
            : $ctx->t('premium.inactive');
        $lines[] = $ctx->t('premium.limits', [
            'likes' => $used['like'], 'likes_max' => $caps['like'],
            'supers' => $used['super'], 'supers_max' => $caps['super'],
        ]);
        $lines[] = $ctx->t('premium.features');
        $lines[] = $ctx->t('limit.utc');
        $rows = [];
        foreach (self::products('premium') as $p) {
            $rows[] = [[$ctx->t('premium.pkg', ['days' => $p['days'], 'price' => $p['price_xtr']]), 'pm:b:' . $p['id']]];
        }
        if (P2p::enabled()) {
            $rows[] = [[$ctx->t('premium.card_btn'), 'pm:card']];
        }
        $rows[] = [[$ctx->t('premium.invite_btn'), 'pm:inv']];
        $rows[] = [[$ctx->t('btn.back'), 'm:home']];
        $ctx->send(implode("\n\n", $lines), Kb::inline($rows));
    }

    public static function boostMenu(Ctx $ctx): void
    {
        $p = self::products('boost')[0] ?? null;
        $lines = [$ctx->t('boost.title')];
        $active = App::db()->all(
            'SELECT audience, MAX(expires_at) AS until FROM tb_boosts WHERE user_id = ? AND expires_at > UTC_TIMESTAMP() GROUP BY audience',
            [$ctx->uid]
        );
        foreach ($active as $a) {
            $lines[] = $ctx->t('boost.active_' . $a['audience'], ['date' => substr((string)$a['until'], 0, 16) . ' UTC']);
        }
        if ($p) {
            $lines[] = $ctx->t('boost.price', ['days' => $p['days'], 'price' => $p['price_xtr']]);
        }
        $lines[] = $ctx->t('boost.no_guarantee');
        $rows = [];
        if ($p) {
            $rows[] = [[$ctx->t('boost.more_f'), 'bs:f']];
            $rows[] = [[$ctx->t('boost.more_m'), 'bs:m']];
        }
        $rows[] = [[$ctx->t('btn.back'), 'm:home']];
        $ctx->send(implode("\n\n", $lines), Kb::inline($rows));
    }

    public static function callback(Ctx $ctx, array $p): void
    {
        $db = App::db();
        if ($p[0] === 'pm' && ($p[1] ?? '') === 'b' && ctype_digit($p[2] ?? '')) {
            $prod = $db->one("SELECT * FROM tb_products WHERE id = ? AND kind = 'premium' AND active = 1", [(int)$p[2]]);
            if (!$prod) {
                $ctx->answer($ctx->t('err.stale'));
                return;
            }
            $ctx->answer();
            self::createOrder($ctx, $prod, null);
            return;
        }
        if ($p[0] === 'pm' && in_array($p[1] ?? '', ['card', 'cb'], true)) {
            P2p::callback($ctx, $p);
            return;
        }
        if ($p[0] === 'pm' && ($p[1] ?? '') === 'menu') {
            $ctx->answer();
            self::premiumMenu($ctx);
            return;
        }
        if ($p[0] === 'pm' && ($p[1] ?? '') === 'inv') {
            $ctx->answer();
            Referrals::command($ctx);
            return;
        }
        if ($p[0] === 'bs' && in_array($p[1] ?? '', ['f', 'm'], true)) {
            $prod = self::products('boost')[0] ?? null;
            if (!$prod) {
                $ctx->answer($ctx->t('err.stale'));
                return;
            }
            $ctx->answer();
            self::createOrder($ctx, $prod, $p[1]);
            return;
        }
        $ctx->answer($ctx->t('err.stale'));
    }

    /** Buyurtma: user_id, product_id, kind, audience, days, amount va currency snapshot. */
    public static function createOrder(Ctx $ctx, array $prod, ?string $audience): string
    {
        $id = bin2hex(random_bytes(16));
        App::db()->exec(
            "INSERT INTO tb_orders (id, user_id, product_id, kind, audience, days, amount, currency, status, created_at, expires_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, 'XTR', 'pending', UTC_TIMESTAMP(), UTC_TIMESTAMP() + INTERVAL " . self::ORDER_TTL_HOURS . " HOUR)",
            [$id, $ctx->uid, (int)$prod['id'], $prod['kind'], $audience, (int)$prod['days'], (int)$prod['price_xtr']]
        );
        if ($prod['kind'] === 'premium') {
            $title = $ctx->t('inv.premium_title', ['days' => $prod['days']]);
            $desc = $ctx->t('inv.premium_desc', ['days' => $prod['days']]);
        } else {
            $title = $ctx->t('inv.boost_title', ['days' => $prod['days']]);
            $desc = $ctx->t('inv.boost_desc_' . $audience, ['days' => $prod['days']]);
        }
        $ctx->api('sendInvoice', [
            'chat_id' => $ctx->uid,
            'title' => mb_substr($title, 0, 32),
            'description' => mb_substr($desc, 0, 255),
            'payload' => $id,
            'provider_token' => '',
            'currency' => 'XTR',
            'prices' => [['label' => mb_substr($title, 0, 32), 'amount' => (int)$prod['price_xtr']]],
        ], null, 2);
        return $id;
    }

    /**
     * Tez yo‘l: outbox va broadcast lockini kutmaydi, qatorlarni qulflamaydi,
     * javobni to‘g‘ridan-to‘g‘ri yuboradi (Telegram 10 soniya ichida javob kutadi).
     */
    public static function preCheckout(int $updateId, array $q): array
    {
        $ok = false;
        $err = 'pay.err_generic';
        $lang = 'uz';
        $db = App::db();
        try {
            $db->exec('INSERT IGNORE INTO tb_processed_updates (update_id, processed_at) VALUES (?, UTC_TIMESTAMP())', [$updateId]);
            $from = (int)($q['from']['id'] ?? 0);
            $payload = (string)($q['invoice_payload'] ?? '');
            $u = $from > 0 ? Users::find($from) : null;
            $lang = Lang::norm($u['lang'] ?? null);
            $o = preg_match('/^[0-9a-f]{32}$/', $payload) ? $db->one('SELECT *, (expires_at > UTC_TIMESTAMP()) AS fresh, (created_at > UTC_TIMESTAMP() - INTERVAL 24 HOUR) AS young FROM tb_orders WHERE id = ?', [$payload]) : null;
            if (!$o) {
                $err = 'pay.err_order';
            } elseif ($o['status'] !== 'pending') {
                $err = 'pay.err_order';
            } elseif ((int)$o['user_id'] !== $from) {
                $err = 'pay.err_order';
            } elseif (($q['currency'] ?? '') !== 'XTR' || $o['currency'] !== 'XTR') {
                $err = 'pay.err_amount';
            } elseif (!is_int($q['total_amount'] ?? null) || $q['total_amount'] !== (int)$o['amount']) {
                $err = 'pay.err_amount';
            } elseif (!(int)$o['fresh'] || !(int)$o['young']) {
                $err = 'pay.err_expired';
            } elseif (!Users::isVisible($u)) {
                $err = 'pay.err_profile';
            } else {
                $ok = true;
            }
        } catch (\Throwable $e) {
            Log::error('pre_checkout', $e);
            $ok = false;
        }
        $params = ['pre_checkout_query_id' => (string)($q['id'] ?? ''), 'ok' => $ok];
        if (!$ok) {
            $params['error_message'] = Lang::t($lang, $err);
        }
        try {
            App::tg()->call('answerPreCheckoutQuery', $params, 5);
        } catch (\Throwable $e) {
            Log::error('answerPreCheckoutQuery', $e);
        }
        return ['status' => 'precheckout', 'ok' => $ok, 'out' => []];
    }

    /** successful_payment: hamma narsa qayta tekshiriladi, xizmat va paid holati bitta tranzaksiyada. */
    public static function success(Ctx $ctx, array $sp): void
    {
        $db = App::db();
        $payload = (string)($sp['invoice_payload'] ?? '');
        $currency = (string)($sp['currency'] ?? '');
        $total = $sp['total_amount'] ?? null;
        $charge = (string)($sp['telegram_payment_charge_id'] ?? '');
        $provider = isset($sp['provider_payment_charge_id']) ? mb_substr((string)$sp['provider_payment_charge_id'], 0, 191) : null;

        $reject = function (string $reason) use ($ctx, $db, $payload, $currency, $total, $charge): void {
            $db->exec(
                'INSERT INTO tb_rejected_payments (order_id, user_id, amount, currency, telegram_payment_charge_id, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, UTC_TIMESTAMP())',
                [mb_substr($payload, 0, 64), $ctx->uid, is_int($total) ? $total : null, mb_substr($currency, 0, 8), $charge !== '' ? mb_substr($charge, 0, 191) : null, $reason]
            );
            Admin::notify($ctx, 'admin.payment_rejected', ['reason' => $reason, 'user' => $ctx->uid, 'amount' => is_int($total) ? $total : '?', 'order' => mb_substr($payload, 0, 40)]);
            $ctx->send($ctx->t('pay.rejected', ['contact' => Router::contact()]));
        };

        if (!preg_match('/^[0-9a-f]{32}$/', $payload)) {
            $reject('bad_payload');
            return;
        }
        if ($charge === '' || strlen($charge) > 191) {
            $reject('bad_charge');
            return;
        }
        $o = $db->one('SELECT * FROM tb_orders WHERE id = ? FOR UPDATE', [$payload]);
        if (!$o) {
            $reject('order_not_found');
            return;
        }
        $used = $db->one('SELECT id FROM tb_orders WHERE telegram_payment_charge_id = ? FOR UPDATE', [$charge]);
        if ($used) {
            if ($used['id'] === $o['id'] && $o['status'] === 'paid') {
                return; // ayni to‘lov qayta keldi: xizmat ikkinchi marta yoqilmaydi
            }
            $reject('charge_reused');
            return;
        }
        if ($o['status'] === 'paid') {
            $reject('order_already_paid');
            return;
        }
        if ((int)$o['user_id'] !== $ctx->uid) {
            $reject('wrong_user');
            return;
        }
        if ($currency !== 'XTR' || $o['currency'] !== 'XTR') {
            $reject('wrong_currency');
            return;
        }
        if (!is_int($total) || $total !== (int)$o['amount']) {
            $reject('wrong_amount');
            return;
        }
        if (!in_array($o['status'], ['pending', 'expired'], true)) {
            $reject('bad_status');
            return;
        }
        $n = $db->exec(
            "UPDATE tb_orders SET status = 'paid', telegram_payment_charge_id = ?, provider_payment_charge_id = ?, paid_at = UTC_TIMESTAMP()
             WHERE id = ? AND status IN ('pending','expired')",
            [$charge, $provider, $o['id']]
        );
        if ($n !== 1) {
            throw new \RuntimeException('order state changed');
        }
        App::hook('after_order_paid');
        if ($o['kind'] === 'premium') {
            $db->exec(
                'UPDATE tb_users SET premium_until = DATE_ADD(GREATEST(COALESCE(premium_until, UTC_TIMESTAMP()), UTC_TIMESTAMP()), INTERVAL ? DAY) WHERE id = ?',
                [(int)$o['days'], $ctx->uid]
            );
            $until = (string)$db->val('SELECT premium_until FROM tb_users WHERE id = ?', [$ctx->uid]);
            $ctx->u['premium_until'] = $until;
            $ctx->send($ctx->t('pay.premium_ok', ['date' => substr($until, 0, 16) . ' UTC']));
        } else {
            $aud = $o['audience'] === 'f' ? 'f' : 'm';
            $start = (string)$db->val(
                'SELECT GREATEST(UTC_TIMESTAMP(), COALESCE(MAX(expires_at), UTC_TIMESTAMP())) FROM tb_boosts WHERE user_id = ? AND audience = ? AND expires_at > UTC_TIMESTAMP()',
                [$ctx->uid, $aud]
            );
            $db->exec(
                'INSERT INTO tb_boosts (user_id, audience, order_id, starts_at, expires_at) VALUES (?, ?, ?, ?, DATE_ADD(?, INTERVAL ? DAY))',
                [$ctx->uid, $aud, $o['id'], $start, $start, (int)$o['days']]
            );
            $until = (string)$db->val('SELECT expires_at FROM tb_boosts WHERE order_id = ?', [$o['id']]);
            $ctx->send($ctx->t('pay.boost_ok_' . $aud, ['date' => substr($until, 0, 16) . ' UTC']));
        }
    }
}
