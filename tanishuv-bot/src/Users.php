<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

final class Users
{
    private const COLS = [
        'lang', 'reg_step', 'age_confirmed', 'name', 'photos', 'gender', 'region', 'interests', 'status',
        'premium_until', 'state', 'state_data', 'card_nonce', 'card_target', 'card_ctx', 'card_pos',
        'search_pref', 'active_chat_id', 'blocked_bot',
    ];

    /** tb_user_ext dagi maydonlar (tb_users ga ALTER qilmaslik uchun alohida jadval). */
    private const EXT = ['age', 'goal', 'verified', 'mod_hidden', 'pref_age_min', 'pref_age_max', 'pref_goal', 'pref_verified'];
    private const SELECT = 'SELECT u.*, x.age, x.goal, COALESCE(x.verified, 0) AS verified, COALESCE(x.mod_hidden, 0) AS mod_hidden,
        x.pref_age_min, x.pref_age_max, x.pref_goal, COALESCE(x.pref_verified, 0) AS pref_verified
        FROM tb_users u LEFT JOIN tb_user_ext x ON x.user_id = u.id WHERE u.id = ?';
    public const GOALS = ['serious', 'friends', 'chat'];

    public const REGIONS = 13;
    public const INTERESTS = ['music', 'sport', 'travel', 'movies', 'books', 'games', 'cooking', 'art', 'tech', 'nature', 'pets', 'fashion'];

    /** Foydalanuvchini qatorini qulflab oladi (yo‘q bo‘lsa yaratadi). Tranzaksiya ichida chaqiriladi. */
    public static function lock(int $id): array
    {
        $db = App::db();
        // Avval X-qulf bilan o‘qiymiz. INSERT IGNORE ni faqat qator yo‘q bo‘lsa chaqiramiz:
        // mavjud qatorda INSERT IGNORE S-qulf oladi va parallel so‘rovlarda deadlock beradi.
        $u = $db->one(self::SELECT . ' FOR UPDATE', [$id]);
        if ($u === null) {
            $db->exec(
                'INSERT IGNORE INTO tb_users (id, created_at, updated_at, last_seen_at) VALUES (?, UTC_TIMESTAMP(), UTC_TIMESTAMP(), UTC_TIMESTAMP())',
                [$id]
            );
            $u = $db->one(self::SELECT . ' FOR UPDATE', [$id]);
        }
        $db->exec('UPDATE tb_users SET last_seen_at = UTC_TIMESTAMP() WHERE id = ?', [$id]);
        return $u;
    }

    public static function find(int $id, bool $forUpdate = false): ?array
    {
        return App::db()->one(self::SELECT . ($forUpdate ? ' FOR UPDATE' : ''), [$id]);
    }

    public static function update(int $id, array $f): void
    {
        $ext = array_intersect_key($f, array_flip(self::EXT));
        $f = array_diff_key($f, $ext);
        if ($ext) {
            self::updateExt($id, $ext);
        }
        if (!$f) {
            return;
        }
        $set = [];
        $p = [];
        foreach ($f as $k => $v) {
            if (!in_array($k, self::COLS, true)) {
                throw new \LogicException('unknown column ' . $k);
            }
            $set[] = "`$k` = ?";
            $p[] = is_bool($v) ? (int)$v : $v;
        }
        $p[] = $id;
        App::db()->exec('UPDATE tb_users SET ' . implode(', ', $set) . ', updated_at = UTC_TIMESTAMP() WHERE id = ?', $p);
    }

    public static function updateExt(int $id, array $f): void
    {
        $cols = [];
        $ph = [];
        $vals = [];
        foreach ($f as $k => $v) {
            if (!in_array($k, self::EXT, true)) {
                throw new \LogicException('unknown ext column ' . $k);
            }
            $cols[] = $k;
            $ph[] = '?';
            $vals[] = is_bool($v) ? (int)$v : $v;
        }
        foreach (['verified' => 'verified_at', 'mod_hidden' => 'hidden_at'] as $flag => $at) {
            if (array_key_exists($flag, $f)) {
                $cols[] = $at;
                $ph[] = 'IF(? = 1, UTC_TIMESTAMP(), NULL)';
                $vals[] = (int)$f[$flag];
            }
        }
        $upd = array_map(static fn($c) => "`$c` = VALUES(`$c`)", $cols);
        App::db()->exec(
            'INSERT INTO tb_user_ext (user_id, `' . implode('`, `', $cols) . '`, updated_at) VALUES (?, ' . implode(', ', $ph) . ', UTC_TIMESTAMP())
             ON DUPLICATE KEY UPDATE ' . implode(', ', $upd) . ', updated_at = VALUES(updated_at)',
            array_merge([$id], $vals)
        );
    }

    public static function age(array $u): ?int
    {
        $a = $u['age'] ?? null;
        return $a === null ? null : (int)$a;
    }

    public static function photos(array $u): array
    {
        $p = json_decode((string)($u['photos'] ?? ''), true);
        return is_array($p) ? array_values(array_filter($p, 'is_string')) : [];
    }

    public static function interests(array $u): array
    {
        $s = trim((string)($u['interests'] ?? ''));
        return $s === '' ? [] : array_values(array_intersect(explode(',', $s), self::INTERESTS));
    }

    public static function isPremium(array $u): bool
    {
        // Har safar real vaqt bilan tekshiriladi (CRON ga bog‘liq emas)
        return !empty($u['premium_until']) && strtotime($u['premium_until'] . ' UTC') > time();
    }

    public static function isComplete(array $u): bool
    {
        return ($u['reg_step'] ?? '') === 'done' && (int)($u['age_confirmed'] ?? 0) === 1;
    }

    public static function isVisible(?array $u): bool
    {
        return $u !== null && self::isComplete($u) && ($u['status'] ?? '') === 'active' && (int)($u['mod_hidden'] ?? 0) === 0;
    }

    public static function validName(string $s): ?string
    {
        $s = trim((string)preg_replace('/\s+/u', ' ', $s));
        if (preg_match('/[\x00-\x1F\x7F]/u', $s)) {
            return null;
        }
        $len = mb_strlen($s);
        return ($len >= 2 && $len <= 40) ? $s : null;
    }
}
