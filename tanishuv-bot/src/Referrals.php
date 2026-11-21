<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Referal: /start ref_<ID>. Taklif qilgan odam, taklif qilingan 18+ anketani to‘liq tugatgach,
 * bir martalik Premium kunlarini oladi. Chegara: ref_max_rewards ta mukofot.
 */
final class Referrals
{
    public static function link(int $uid): ?string
    {
        $bot = ltrim(trim((string)App::cfg('bot_username', '')), '@');
        return $bot === '' ? null : 'https://t.me/' . $bot . '?start=ref_' . $uid;
    }

    /** /start payload: faqat yangi (hali til tanlamagan) foydalanuvchi uchun yoziladi. */
    public static function capture(Ctx $ctx, string $arg): void
    {
        if (!preg_match('/^ref_(\d{1,15})$/', $arg, $m) || ($ctx->u['reg_step'] ?? 'lang') !== 'lang' || !empty($ctx->u['lang'])) {
            return;
        }
        $inviter = (int)$m[1];
        if ($inviter <= 0 || $inviter === $ctx->uid) {
            return;
        }
        $iu = Users::find($inviter);
        if (!$iu || !Users::isComplete($iu)) {
            return;
        }
        App::db()->exec('INSERT IGNORE INTO tb_referrals (invited_id, inviter_id, created_at) VALUES (?, ?, UTC_TIMESTAMP())', [$ctx->uid, $inviter]);
    }

    /** Ro‘yxatdan o‘tish tugaganda chaqiriladi. */
    public static function reward(Ctx $ctx): void
    {
        $db = App::db();
        $days = max(0, min(30, Settings::int('ref_reward_days')));
        $r = $db->one('SELECT * FROM tb_referrals WHERE invited_id = ? AND rewarded_at IS NULL FOR UPDATE', [$ctx->uid]);
        if (!$r || $days <= 0) {
            return;
        }
        $inviter = (int)$r['inviter_id'];
        $done = (int)$db->val('SELECT COUNT(*) FROM tb_referrals WHERE inviter_id = ? AND rewarded_at IS NOT NULL', [$inviter]);
        if ($done >= max(0, Settings::int('ref_max_rewards'))) {
            return;
        }
        $iu = Users::find($inviter, true);
        if (!$iu || ($iu['status'] ?? '') !== 'active') {
            return;
        }
        $db->exec('UPDATE tb_referrals SET rewarded_at = UTC_TIMESTAMP() WHERE invited_id = ? AND rewarded_at IS NULL', [$ctx->uid]);
        $db->exec(
            "UPDATE tb_users SET premium_until = GREATEST(COALESCE(premium_until, UTC_TIMESTAMP()), UTC_TIMESTAMP()) + INTERVAL $days DAY WHERE id = ?",
            [$inviter]
        );
        $l = Lang::norm($iu['lang'] ?? null);
        $ctx->api('sendMessage', ['chat_id' => $inviter, 'text' => Lang::t($l, 'invite.reward', ['days' => $days])], $inviter);
    }

    public static function command(Ctx $ctx): void
    {
        $days = Settings::int('ref_reward_days');
        $link = self::link($ctx->uid);
        $db = App::db();
        $joined = (int)$db->val('SELECT COUNT(*) FROM tb_referrals WHERE inviter_id = ?', [$ctx->uid]);
        $paid = (int)$db->val('SELECT COUNT(*) FROM tb_referrals WHERE inviter_id = ? AND rewarded_at IS NOT NULL', [$ctx->uid]);
        $ctx->send($ctx->t($link ? 'invite.text' : 'invite.nolink', ['days' => $days, 'link' => (string)$link, 'joined' => $joined, 'paid' => $paid]));
    }
}
