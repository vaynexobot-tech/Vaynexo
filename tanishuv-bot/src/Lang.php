<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

final class Lang
{
    public const LANGS = ['uz', 'ru', 'en'];
    private static array $cache = [];

    public static function all(string $lang): array
    {
        if (!in_array($lang, self::LANGS, true)) {
            $lang = 'uz';
        }
        if (!isset(self::$cache[$lang])) {
            self::$cache[$lang] = require TB_ROOT . '/locales/' . $lang . '.php';
        }
        return self::$cache[$lang];
    }

    public static function t(string $lang, string $key, array $p = []): string
    {
        $s = self::all($lang)[$key] ?? self::all('uz')[$key] ?? $key;
        if ($p) {
            $r = [];
            foreach ($p as $k => $v) {
                $r['{' . $k . '}'] = (string)$v;
            }
            $s = strtr($s, $r);
        }
        return $s;
    }

    public static function norm(?string $code): string
    {
        return in_array($code, self::LANGS, true) ? $code : 'uz';
    }
}
