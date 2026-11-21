<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/** Admin paneldan o‘zgartiriladigan sozlamalar (tb_settings). Qiymat yo‘q bo‘lsa — standart. */
final class Settings
{
    public const DEFAULTS = [
        'age_min' => '18',
        'age_max' => '99',
        'likemsg_mode' => 'on',      // on | moderate | off
        'likemsg_links' => '1',      // 1 = havola va @username bloklanadi
        'likemsg_stopwords' => '',
        'verify_enabled' => '1',
        'autohide_reports' => '3',   // 0 = o‘chiq
        'autohide_days' => '30',
        'likes_gate' => '1',         // 1 = «Yoqdi bosganlar» ro‘yxati faqat Premium uchun
        'photo_review' => '0',       // 1 = yangi anketalar admin navbatiga tushadi (post-moderatsiya)
        'retention' => '1',          // 1 = CRON qaytarish eslatmalarini yuboradi
        'ref_reward_days' => '1',
        'ref_max_rewards' => '30',
    ];
    public const LIKEMSG_MODES = ['on', 'moderate', 'off'];

    public static function get(string $k): string
    {
        return (string)App::db()->setting($k, self::DEFAULTS[$k] ?? '');
    }

    public static function int(string $k): int
    {
        return (int)self::get($k);
    }

    public static function on(string $k): bool
    {
        return self::get($k) === '1';
    }

    public static function set(string $k, string $v): void
    {
        if (!array_key_exists($k, self::DEFAULTS)) {
            throw new \LogicException('unknown setting ' . $k);
        }
        App::db()->setSetting($k, $v);
    }

    /** [min, max] — har doim 18..99 oralig‘ida. */
    public static function ageRange(): array
    {
        $min = max(18, min(99, self::int('age_min')));
        $max = max($min, min(99, self::int('age_max')));
        return [$min, $max];
    }

    public static function likeMsgMode(): string
    {
        $m = self::get('likemsg_mode');
        return in_array($m, self::LIKEMSG_MODES, true) ? $m : 'on';
    }

    /** @return string[] kichik harfdagi taqiqlangan so‘zlar */
    public static function stopwords(): array
    {
        $out = [];
        foreach (preg_split('/[,\n;]+/u', self::get('likemsg_stopwords')) ?: [] as $w) {
            $w = mb_strtolower(trim($w));
            if ($w !== '' && mb_strlen($w) <= 40) {
                $out[$w] = true;
            }
        }
        return array_slice(array_keys($out), 0, 200);
    }
}
