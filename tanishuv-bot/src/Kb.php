<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

final class Kb
{
    /** @param array $rows [[ [text, data], ... ], ...] */
    public static function inline(array $rows): array
    {
        $out = [];
        foreach ($rows as $row) {
            $r = [];
            foreach ($row as $b) {
                if ($b === null) {
                    continue;
                }
                if (($b[2] ?? null) === 'url') {
                    $r[] = ['text' => $b[0], 'url' => $b[1]];
                    continue;
                }
                if (strlen($b[1]) > 64) {
                    throw new \LogicException('callback_data 64 baytdan oshdi: ' . $b[1]);
                }
                $r[] = ['text' => $b[0], 'callback_data' => $b[1]];
            }
            if ($r) {
                $out[] = $r;
            }
        }
        return ['inline_keyboard' => $out];
    }

    public static function reply(array $rows): array
    {
        $out = [];
        foreach ($rows as $row) {
            $out[] = array_map(static fn($t) => ['text' => $t], $row);
        }
        return ['keyboard' => $out, 'resize_keyboard' => true, 'is_persistent' => true];
    }

    public static function remove(): array
    {
        return ['remove_keyboard' => true];
    }
}
