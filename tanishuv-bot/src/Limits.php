<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/** Kunlik like / super like limitlari. Kun UTC bo‘yicha hisoblanadi (00:00 UTC = Toshkent 05:00). */
final class Limits
{
    public static function caps(array $u): array
    {
        $p = Users::isPremium($u);
        return [
            'like' => (int)App::cfg($p ? 'limits.premium_likes' : 'limits.free_likes', $p ? 300 : 30),
            'super' => (int)App::cfg($p ? 'limits.premium_supers' : 'limits.free_supers', $p ? 10 : 1),
        ];
    }

    public static function used(int $uid): array
    {
        $r = App::db()->one('SELECT likes, supers FROM tb_daily_limits WHERE user_id = ? AND day = UTC_DATE()', [$uid]);
        return ['like' => (int)($r['likes'] ?? 0), 'super' => (int)($r['supers'] ?? 0)];
    }

    public static function consume(Ctx $ctx, string $kind): bool
    {
        $db = App::db();
        $db->exec('INSERT IGNORE INTO tb_daily_limits (user_id, day, likes, supers) VALUES (?, UTC_DATE(), 0, 0)', [$ctx->uid]);
        $r = $db->one('SELECT likes, supers FROM tb_daily_limits WHERE user_id = ? AND day = UTC_DATE() FOR UPDATE', [$ctx->uid]);
        $caps = self::caps($ctx->u);
        $col = $kind === 'like' ? 'likes' : 'supers';
        if ((int)$r[$col] >= $caps[$kind]) {
            $ctx->answer($ctx->t($kind === 'like' ? 'limit.likes' : 'limit.supers', ['n' => $caps[$kind]]), true);
            $ctx->send($ctx->t($kind === 'like' ? 'limit.likes' : 'limit.supers', ['n' => $caps[$kind]]) . "\n" . $ctx->t('limit.utc'));
            return false;
        }
        $db->exec("UPDATE tb_daily_limits SET $col = $col + 1 WHERE user_id = ? AND day = UTC_DATE()", [$ctx->uid]);
        return true;
    }
}
