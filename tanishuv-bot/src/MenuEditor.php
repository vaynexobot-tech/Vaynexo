<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Bosh menyu muharriri. O‘zgarishlar har admin uchun alohida qoralamada saqlanadi.
 * Saqlashdan oldin uch tildagi preview majburiy. menu_version optimistik qulf vazifasini bajaradi:
 * eski versiyaga asoslangan qoralama yangi menyuni bosib keta olmaydi.
 */
final class MenuEditor
{
    private static function key(Ctx $ctx): string
    {
        return 'menu_draft:' . $ctx->uid;
    }

    public static function load(Ctx $ctx): ?array
    {
        $raw = App::db()->setting(self::key($ctx));
        $d = $raw ? json_decode($raw, true) : null;
        return is_array($d) && isset($d['items'], $d['base']) ? $d : null;
    }

    public static function ensure(Ctx $ctx): array
    {
        $d = self::load($ctx);
        if ($d === null) {
            $d = ['base' => Menu::version(), 'items' => Menu::live(), 'previewed' => null];
            self::store($ctx, $d);
        }
        return $d;
    }

    private static function store(Ctx $ctx, array $d): void
    {
        App::db()->setSetting(self::key($ctx), json_encode($d, JSON_UNESCAPED_UNICODE));
    }

    private static function changed(Ctx $ctx, array $d): void
    {
        $d['previewed'] = null;
        self::store($ctx, $d);
    }

    public static function hash(array $items): string
    {
        return sha1(json_encode(array_values($items), JSON_UNESCAPED_UNICODE));
    }

    private static function idx(array $items, string $id): ?int
    {
        foreach ($items as $i => $it) {
            if ($it['id'] === $id) {
                return $i;
            }
        }
        return null;
    }

    public static function callback(Ctx $ctx, array $p): void
    {
        $a = $p[1];
        $id = $p[2] ?? '';
        if ($a === 'mx') {
            App::db()->deleteSetting(self::key($ctx));
            if (str_starts_with((string)($ctx->u['state'] ?? ''), 'adm:m')) {
                $ctx->setState(null);
            }
            Admin::audit($ctx, 'menu.discard');
            $ctx->send($ctx->t('adm.menu_discarded'), Kb::inline([[[$ctx->t('btn.back'), 'a:h']]]));
            return;
        }
        $d = self::ensure($ctx);
        $items = $d['items'];
        $i = $id !== '' ? self::idx($items, $id) : null;
        switch ($a) {
            case 'me':
                self::showList($ctx, $d);
                return;
            case 'mi':
                $i === null ? self::showList($ctx, $d) : self::showItem($ctx, $items[$i]);
                return;
            case 'mr':
                if ($i === null) {
                    break;
                }
                $ctx->setState('adm:mlabel', ['item' => $id, 'mode' => 'rename', 'step' => 'uz', 'vals' => []]);
                $ctx->send($ctx->t('adm.menu_label_prompt', ['lang' => 'UZ', 'cur' => $items[$i]['label']['uz'] ?? '']));
                return;
            case 'mm':
                if ($i === null) {
                    break;
                }
                $ctx->setState('adm:mpos', ['item' => $id]);
                $ctx->send($ctx->t('adm.menu_pos_prompt', ['row' => $items[$i]['row'], 'col' => $items[$i]['col']]));
                return;
            case 'ma':
                if ($i === null || in_array($id, Menu::CORE, true)) {
                    $ctx->send($ctx->t('adm.menu_core_locked'));
                    return;
                }
                $rows = [];
                foreach (Menu::ACTIONS as $act) {
                    $rows[] = [[($items[$i]['action'] === $act ? '✅ ' : '') . $ctx->t('adm.act_' . $act), 'a:ms:' . $id . ':' . $act]];
                }
                $rows[] = [[$ctx->t('btn.back'), 'a:mi:' . $id]];
                $ctx->send($ctx->t('adm.menu_action_prompt'), Kb::inline($rows));
                return;
            case 'ms':
                $act = $p[3] ?? '';
                if ($i === null || in_array($id, Menu::CORE, true) || !in_array($act, Menu::ACTIONS, true)) {
                    $ctx->send($ctx->t('adm.menu_core_locked'));
                    return;
                }
                $items[$i]['action'] = $act;
                $d['items'] = $items;
                self::changed($ctx, $d);
                if ($act === 'text' && empty($items[$i]['text'])) {
                    $ctx->setState('adm:mtext', ['item' => $id, 'step' => 'uz', 'vals' => []]);
                    $ctx->send($ctx->t('adm.menu_text_prompt', ['lang' => 'UZ']));
                    return;
                }
                self::showItem($ctx, $items[$i]);
                return;
            case 'mt':
                if ($i === null || in_array($id, Menu::CORE, true)) {
                    $ctx->send($ctx->t('adm.menu_core_locked'));
                    return;
                }
                $ctx->setState('adm:mtext', ['item' => $id, 'step' => 'uz', 'vals' => []]);
                $ctx->send($ctx->t('adm.menu_text_prompt', ['lang' => 'UZ']));
                return;
            case 'md':
                if ($i === null || in_array($id, Menu::CORE, true)) {
                    $ctx->send($ctx->t('adm.menu_core_locked'));
                    return;
                }
                array_splice($items, $i, 1);
                $d['items'] = $items;
                self::changed($ctx, $d);
                self::showList($ctx, $d);
                return;
            case 'mn':
                if (count($items) >= Menu::MAX_ITEMS) {
                    $ctx->send($ctx->t('adm.menu_full', ['max' => Menu::MAX_ITEMS]));
                    return;
                }
                $ctx->setState('adm:mlabel', ['item' => null, 'mode' => 'new', 'step' => 'uz', 'vals' => []]);
                $ctx->send($ctx->t('adm.menu_label_prompt', ['lang' => 'UZ', 'cur' => '—']));
                return;
            case 'mp':
                $err = self::validate($items);
                if ($err !== null) {
                    $ctx->send($ctx->t('adm.menu_invalid', ['err' => $err]));
                    return;
                }
                $parts = [];
                foreach (Lang::LANGS as $l) {
                    $lines = [];
                    foreach (Menu::rows($items, $l) as $row) {
                        $lines[] = implode(' | ', array_map(static fn($t) => '[' . $t . ']', $row));
                    }
                    $parts[] = strtoupper($l) . ":\n" . implode("\n", $lines);
                }
                $d['previewed'] = self::hash($items);
                self::store($ctx, $d);
                $ctx->send($ctx->t('adm.menu_preview') . "\n\n" . implode("\n\n", $parts), Kb::inline([
                    [[$ctx->t('btn.save'), 'a:mv']],
                    [[$ctx->t('btn.back'), 'a:me']],
                ]));
                return;
            case 'mv':
                self::save($ctx, $d);
                return;
        }
        $ctx->send($ctx->t('err.stale'));
    }

    private static function showList(Ctx $ctx, array $d): void
    {
        $rows = [];
        foreach (Menu::sorted($d['items']) as $it) {
            $rows[] = [[$it['row'] . '.' . $it['col'] . ' ' . ($it['label'][$ctx->lang] ?? $it['id']), 'a:mi:' . $it['id']]];
        }
        $rows[] = [[$ctx->t('adm.menu_add'), 'a:mn'], [$ctx->t('adm.menu_preview_btn'), 'a:mp']];
        $rows[] = [[$ctx->t('btn.save'), 'a:mv'], [$ctx->t('adm.menu_discard'), 'a:mx']];
        $rows[] = [[$ctx->t('btn.back'), 'a:h']];
        $ctx->send($ctx->t('adm.menu_title', ['base' => $d['base'], 'live' => Menu::version(), 'n' => count($d['items']), 'max' => Menu::MAX_ITEMS]), Kb::inline($rows));
    }

    private static function showItem(Ctx $ctx, array $it): void
    {
        $core = in_array($it['id'], Menu::CORE, true);
        $txt = $ctx->t('adm.menu_item', [
            'id' => $it['id'],
            'action' => $it['action'],
            'uz' => $it['label']['uz'] ?? '', 'ru' => $it['label']['ru'] ?? '', 'en' => $it['label']['en'] ?? '',
            'row' => $it['row'], 'col' => $it['col'],
        ]);
        $rows = [
            [[$ctx->t('adm.menu_rename'), 'a:mr:' . $it['id']], [$ctx->t('adm.menu_move'), 'a:mm:' . $it['id']]],
        ];
        if (!$core) {
            $rows[] = [[$ctx->t('adm.menu_action'), 'a:ma:' . $it['id']], [$ctx->t('adm.menu_text'), 'a:mt:' . $it['id']]];
            $rows[] = [[$ctx->t('adm.menu_delete'), 'a:md:' . $it['id']]];
        }
        $rows[] = [[$ctx->t('btn.back'), 'a:me']];
        $ctx->send($txt, Kb::inline($rows));
    }

    public static function labelError(array $items, string $label, ?string $selfId): ?string
    {
        if (mb_strlen($label) < 1 || mb_strlen($label) > 32 || str_starts_with($label, '/')) {
            return 'label';
        }
        foreach ($items as $it) {
            if ($it['id'] === $selfId) {
                continue;
            }
            if (in_array($label, array_values((array)$it['label']), true)) {
                return 'duplicate';
            }
        }
        return null;
    }

    public static function validate(array $items): ?string
    {
        if (count($items) > Menu::MAX_ITEMS) {
            return 'max ' . Menu::MAX_ITEMS;
        }
        $pos = [];
        $labels = [];
        $ids = [];
        foreach ($items as $it) {
            $ids[] = $it['id'];
            $r = (int)$it['row'];
            $c = (int)$it['col'];
            if ($r < 1 || $r > Menu::MAX_ROW || $c < 1 || $c > Menu::MAX_COL) {
                return 'position ' . $it['id'];
            }
            if (isset($pos["$r.$c"])) {
                return "position $r.$c";
            }
            $pos["$r.$c"] = true;
            if (!in_array($it['action'], Menu::ACTIONS, true)) {
                return 'action ' . $it['id'];
            }
            foreach (Lang::LANGS as $l) {
                $lb = (string)($it['label'][$l] ?? '');
                if ($lb === '' || mb_strlen($lb) > 32) {
                    return 'label ' . $it['id'];
                }
                if (isset($labels[$lb]) && $labels[$lb] !== $it['id']) {
                    return 'duplicate ' . $lb;
                }
                $labels[$lb] = $it['id'];
                if ($it['action'] === 'text' && trim((string)($it['text'][$l] ?? '')) === '') {
                    return 'text ' . $it['id'];
                }
            }
        }
        foreach (Menu::CORE as $core) {
            $it = Menu::findItem($items, $core);
            if ($it === null || $it['action'] !== $core) {
                return 'core ' . $core;
            }
        }
        return null;
    }

    private static function save(Ctx $ctx, array $d): void
    {
        $items = $d['items'];
        $err = self::validate($items);
        if ($err !== null) {
            $ctx->send($ctx->t('adm.menu_invalid', ['err' => $err]));
            return;
        }
        if (($d['previewed'] ?? null) !== self::hash($items)) {
            $ctx->send($ctx->t('adm.menu_preview_first'), Kb::inline([[[$ctx->t('adm.menu_preview_btn'), 'a:mp']]]));
            return;
        }
        $db = App::db();
        $db->exec("INSERT IGNORE INTO tb_settings (name, value, updated_at) VALUES ('menu_version', '1', UTC_TIMESTAMP())");
        $ver = (int)$db->val("SELECT value FROM tb_settings WHERE name = 'menu_version' FOR UPDATE");
        if ((int)$d['base'] !== $ver) {
            $ctx->send($ctx->t('adm.menu_conflict', ['base' => $d['base'], 'live' => $ver]), Kb::inline([[[$ctx->t('adm.menu_discard'), 'a:mx']]]));
            return;
        }
        Menu::reset();
        $old = Menu::live();
        $newLabels = [];
        foreach ($items as $it) {
            foreach (Lang::LANGS as $l) {
                $newLabels[] = (string)$it['label'][$l];
            }
        }
        // Eski nomlar alias sifatida saqlanadi: eski klaviaturadagi tugma ishlashda davom etadi
        foreach ($old as $oi) {
            if (Menu::findItem($items, $oi['id']) === null) {
                continue;
            }
            foreach (Lang::LANGS as $l) {
                $lbl = (string)($oi['label'][$l] ?? '');
                if ($lbl !== '' && !in_array($lbl, $newLabels, true) && mb_strlen($lbl) <= 64) {
                    $db->exec(
                        'INSERT INTO tb_menu_aliases (label, item_id, created_at) VALUES (?, ?, UTC_TIMESTAMP())
                         ON DUPLICATE KEY UPDATE item_id = VALUES(item_id)',
                        [$lbl, $oi['id']]
                    );
                }
            }
        }
        // Jonli nom aliasdan ustun: to‘qnashgan aliaslarni o‘chiramiz
        foreach (array_unique($newLabels) as $lbl) {
            $db->exec('DELETE FROM tb_menu_aliases WHERE label = ?', [$lbl]);
        }
        $db->setSetting('menu_live', json_encode(array_values($items), JSON_UNESCAPED_UNICODE));
        $db->setSetting('menu_version', (string)($ver + 1));
        $db->deleteSetting(self::key($ctx));
        Menu::reset();
        Admin::audit($ctx, 'menu.save', 'v' . ($ver + 1));
        $ctx->send($ctx->t('adm.menu_saved', ['v' => $ver + 1]), Menu::keyboard($ctx->lang));
    }

    public static function input(Ctx $ctx, string $text): void
    {
        $state = (string)$ctx->u['state'];
        $s = $ctx->stateData();
        $d = self::ensure($ctx);
        $items = $d['items'];
        $id = $s['item'] ?? null;
        $i = $id !== null ? self::idx($items, (string)$id) : null;
        if ($id !== null && $i === null) {
            $ctx->setState(null);
            $ctx->send($ctx->t('err.stale'));
            return;
        }
        $order = ['uz' => 'ru', 'ru' => 'en', 'en' => null];
        if ($state === 'adm:mlabel') {
            $err = self::labelError($items, $text, $id);
            if ($err !== null) {
                $ctx->send($ctx->t('adm.menu_label_' . $err));
                return;
            }
            $step = $s['step'] ?? 'uz';
            $s['vals'][$step] = $text;
            if ($order[$step] !== null) {
                $s['step'] = $order[$step];
                $ctx->setState('adm:mlabel', $s);
                $cur = $i !== null ? ($items[$i]['label'][$order[$step]] ?? '') : '—';
                $ctx->send($ctx->t('adm.menu_label_prompt', ['lang' => strtoupper($order[$step]), 'cur' => $cur]));
                return;
            }
            if (($s['mode'] ?? '') === 'rename' && $i !== null) {
                $items[$i]['label'] = $s['vals'];
                $item = $items[$i];
            } else {
                if (count($items) >= Menu::MAX_ITEMS) {
                    $ctx->setState(null);
                    $ctx->send($ctx->t('adm.menu_full', ['max' => Menu::MAX_ITEMS]));
                    return;
                }
                [$r, $c] = self::freeSlot($items);
                $item = ['id' => 'c' . bin2hex(random_bytes(3)), 'action' => 'text', 'label' => $s['vals'], 'text' => null, 'row' => $r, 'col' => $c];
                $items[] = $item;
            }
            $d['items'] = $items;
            self::changed($ctx, $d);
            $ctx->setState(null);
            self::showItem($ctx, $item);
            return;
        }
        if ($state === 'adm:mpos' && $i !== null) {
            if (!preg_match('/^(\d{1,2})\s*[ ,.:x×\/-]?\s*(\d)$/u', $text, $m)) {
                $ctx->send($ctx->t('adm.menu_pos_bad'));
                return;
            }
            $r = (int)$m[1];
            $c = (int)$m[2];
            if ($r < 1 || $r > Menu::MAX_ROW || $c < 1 || $c > Menu::MAX_COL) {
                $ctx->send($ctx->t('adm.menu_pos_bad'));
                return;
            }
            foreach ($items as $j => $it) {
                if ($j !== $i && (int)$it['row'] === $r && (int)$it['col'] === $c) {
                    $ctx->send($ctx->t('adm.menu_pos_busy'));
                    return;
                }
            }
            $items[$i]['row'] = $r;
            $items[$i]['col'] = $c;
            $d['items'] = $items;
            self::changed($ctx, $d);
            $ctx->setState(null);
            self::showItem($ctx, $items[$i]);
            return;
        }
        if ($state === 'adm:mtext' && $i !== null) {
            if (mb_strlen($text) > 1000) {
                $ctx->send($ctx->t('adm.bad_length', ['max' => 1000]));
                return;
            }
            $step = $s['step'] ?? 'uz';
            $s['vals'][$step] = $text;
            if ($order[$step] !== null) {
                $s['step'] = $order[$step];
                $ctx->setState('adm:mtext', $s);
                $ctx->send($ctx->t('adm.menu_text_prompt', ['lang' => strtoupper($order[$step])]));
                return;
            }
            $items[$i]['text'] = $s['vals'];
            $items[$i]['action'] = 'text';
            $d['items'] = $items;
            self::changed($ctx, $d);
            $ctx->setState(null);
            self::showItem($ctx, $items[$i]);
            return;
        }
        $ctx->setState(null);
        self::showList($ctx, $d);
    }

    private static function freeSlot(array $items): array
    {
        $busy = [];
        foreach ($items as $it) {
            $busy[$it['row'] . '.' . $it['col']] = true;
        }
        $maxRow = 0;
        foreach ($items as $it) {
            $maxRow = max($maxRow, (int)$it['row']);
        }
        for ($r = max(1, $maxRow); $r <= Menu::MAX_ROW; $r++) {
            for ($c = 1; $c <= Menu::MAX_COL; $c++) {
                if (!isset($busy["$r.$c"])) {
                    return [$r, $c];
                }
            }
        }
        for ($r = 1; $r <= Menu::MAX_ROW; $r++) {
            for ($c = 1; $c <= Menu::MAX_COL; $c++) {
                if (!isset($busy["$r.$c"])) {
                    return [$r, $c];
                }
            }
        }
        return [Menu::MAX_ROW, Menu::MAX_COL];
    }
}
