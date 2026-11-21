<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Jonli bosh menyu (reply keyboard). Har tugmaning ichki ID si va action i
 * ko‘rinadigan nomidan mustaqil. Eski nomlar tb_menu_aliases orqali ishlaydi.
 */
final class Menu
{
    public const CORE = ['search', 'likes', 'profile', 'premium', 'boost'];
    /** Yangi tugmaga bog‘lanadigan amallar */
    public const ACTIONS = ['search', 'likes', 'profile', 'premium', 'boost', 'saved', 'language', 'support', 'terms', 'privacy', 'paysupport', 'text'];
    public const MAX_ITEMS = 24;
    public const MAX_ROW = 12;
    public const MAX_COL = 3;

    private static ?array $cache = null;

    public static function reset(): void
    {
        self::$cache = null;
    }

    public static function defaults(): array
    {
        $pos = ['search' => [1, 1], 'likes' => [2, 1], 'profile' => [3, 1], 'premium' => [4, 1], 'boost' => [4, 2]];
        $items = [];
        foreach (self::CORE as $id) {
            $label = [];
            foreach (Lang::LANGS as $l) {
                $label[$l] = Lang::t($l, 'menu.' . $id);
            }
            $items[] = ['id' => $id, 'action' => $id, 'label' => $label, 'text' => null, 'row' => $pos[$id][0], 'col' => $pos[$id][1]];
        }
        return $items;
    }

    public static function live(): array
    {
        if (self::$cache === null) {
            $raw = App::db()->setting('menu_live');
            $items = $raw ? json_decode($raw, true) : null;
            self::$cache = is_array($items) && $items ? $items : self::defaults();
        }
        return self::$cache;
    }

    public static function version(): int
    {
        return (int)(App::db()->setting('menu_version', '1'));
    }

    public static function sorted(array $items): array
    {
        usort($items, static fn($a, $b) => [$a['row'], $a['col']] <=> [$b['row'], $b['col']]);
        return $items;
    }

    public static function rows(array $items, string $lang): array
    {
        $rows = [];
        foreach (self::sorted($items) as $it) {
            $rows[(int)$it['row']][] = (string)($it['label'][$lang] ?? $it['label']['uz'] ?? $it['id']);
        }
        ksort($rows);
        return array_values($rows);
    }

    public static function keyboard(string $lang): array
    {
        return Kb::reply(self::rows(self::live(), $lang));
    }

    public static function findItem(array $items, string $id): ?array
    {
        foreach ($items as $it) {
            if ($it['id'] === $id) {
                return $it;
            }
        }
        return null;
    }

    public static function resolve(string $text): ?array
    {
        $items = self::live();
        foreach ($items as $it) {
            foreach (Lang::LANGS as $l) {
                if (($it['label'][$l] ?? null) === $text) {
                    return $it;
                }
            }
        }
        if (mb_strlen($text) > 64) {
            return null;
        }
        $id = App::db()->val('SELECT item_id FROM tb_menu_aliases WHERE label = ?', [$text]);
        return $id === null ? null : self::findItem($items, (string)$id);
    }

    public static function home(Ctx $ctx, string $key = 'menu.title'): void
    {
        $ctx->send($ctx->t($key), self::keyboard($ctx->lang));
    }

    public static function open(Ctx $ctx, array $item): void
    {
        $a = (string)$item['action'];
        if (in_array($a, ['search', 'likes', 'profile', 'premium', 'boost', 'saved'], true) && ($ctx->u['status'] ?? '') !== 'active') {
            $ctx->send($ctx->t('err.suspended'));
            return;
        }
        switch ($a) {
            case 'search':
                Search::menu($ctx);
                return;
            case 'likes':
                Search::likesMenu($ctx);
                return;
            case 'profile':
                Profile::menu($ctx);
                return;
            case 'premium':
                Payments::premiumMenu($ctx);
                return;
            case 'boost':
                Payments::boostMenu($ctx);
                return;
            case 'saved':
                Search::startList($ctx, 'sv');
                return;
            case 'language':
                Registration::askLang($ctx, true);
                return;
            case 'support':
            case 'terms':
            case 'privacy':
            case 'paysupport':
                Router::command($ctx, $a);
                return;
            case 'text':
                $t = (string)($item['text'][$ctx->lang] ?? $item['text']['uz'] ?? '');
                $ctx->send($t !== '' ? $t : '…');
                return;
        }
        self::home($ctx);
    }
}
