<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Foydalanuvchi bloklari. Blok ikki tomonlama ishlaydi: bloklagan ham, bloklangan ham
 * bir-birini qidiruvda, ro‘yxatlarda ko‘rmaydi, like/match/suhbat boshlay olmaydi.
 */
final class Blocks
{
    /** SQL sharti: $col — nomzod ID ustuni. Parametrlar: [me, me] (ikki marta). */
    public static function notBlockedSql(string $col): string
    {
        return "NOT EXISTS (SELECT 1 FROM tb_blocks bl WHERE (bl.blocker_id = ? AND bl.blocked_id = $col) OR (bl.blocker_id = $col AND bl.blocked_id = ?))";
    }

    public static function between(int $a, int $b): bool
    {
        return App::db()->val(
            'SELECT 1 FROM tb_blocks WHERE (blocker_id = ? AND blocked_id = ?) OR (blocker_id = ? AND blocked_id = ?) LIMIT 1',
            [$a, $b, $b, $a]
        ) !== null;
    }

    public static function count(int $uid): int
    {
        return (int)App::db()->val('SELECT COUNT(*) FROM tb_blocks WHERE blocker_id = ?', [$uid]);
    }

    /** Bloklaydi. Faol suhbat bo‘lsa tugatadi. true = yangi blok yozildi. */
    public static function add(Ctx $ctx, int $target): bool
    {
        if ($target <= 0 || $target === $ctx->uid) {
            return false;
        }
        $n = App::db()->exec('INSERT IGNORE INTO tb_blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, UTC_TIMESTAMP())', [$ctx->uid, $target]);
        $cid = (int)App::db()->val(
            "SELECT id FROM tb_chats WHERE status = 'active' AND ((user_a = ? AND user_b = ?) OR (user_a = ? AND user_b = ?)) LIMIT 1",
            [$ctx->uid, $target, $target, $ctx->uid]
        );
        if ($cid > 0) {
            Chat::end($ctx, $cid, 'block', false);
        }
        return $n > 0;
    }

    public static function command(Ctx $ctx): void
    {
        $n = self::count($ctx->uid);
        $rows = $n > 0 ? [[[$ctx->t('blocks.clear'), 'bk:clear']]] : [];
        $ctx->send($ctx->t('blocks.info', ['n' => $n]), $rows ? Kb::inline($rows) : null);
    }

    public static function callback(Ctx $ctx, array $p): void
    {
        if (($p[1] ?? '') !== 'clear') {
            $ctx->answer($ctx->t('err.stale'));
            return;
        }
        App::db()->exec('DELETE FROM tb_blocks WHERE blocker_id = ?', [$ctx->uid]);
        $ctx->answer();
        $ctx->edit($ctx->t('blocks.cleared'));
    }
}
