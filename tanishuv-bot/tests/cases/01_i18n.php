<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\Lang;
use TB\Users;

$t('i18n: UZ/RU/EN kalitlari teng', function () {
    $uz = array_keys(Lang::all('uz'));
    foreach (['ru', 'en'] as $l) {
        $o = array_keys(Lang::all($l));
        T::eq(array_values(array_diff($uz, $o)), [], "$l da yetishmagan kalitlar");
        T::eq(array_values(array_diff($o, $uz)), [], "$l da ortiqcha kalitlar");
    }
});

$t('i18n: placeholderlar teng', function () {
    $ph = static function (string $s): array {
        preg_match_all('/\{([a-z_]+)\}/', $s, $m);
        $r = array_unique($m[1]);
        sort($r);
        return $r;
    };
    foreach (Lang::all('uz') as $k => $v) {
        foreach (['ru', 'en'] as $l) {
            T::eq($ph(Lang::all($l)[$k] ?? ''), $ph($v), "placeholder $l:$k");
        }
    }
});

$t('i18n: koddagi barcha kalitlar tarjimada bor', function () {
    $keys = Lang::all('uz');
    $missing = [];
    foreach (glob(TB_ROOT . '/src/*.php') as $f) {
        $src = (string)file_get_contents($f);
        preg_match_all("/(?:->t|Lang::t)\((?:[^,()]+, )?'([a-z_]+\.[a-z0-9_]+)'(?!\s*\.)/", $src, $m);
        foreach ($m[1] as $k) {
            if (!isset($keys[$k])) {
                $missing[] = basename($f) . ':' . $k;
            }
        }
        preg_match_all("/\? '([a-z_]+\.[a-z0-9_]+)' : '([a-z_]+\.[a-z0-9_]+)'/", $src, $m2);
        foreach (array_merge($m2[1], $m2[2]) as $k) {
            if (!str_starts_with($k, 'limits.') && !isset($keys[$k])) {
                $missing[] = basename($f) . ':' . $k;
            }
        }
    }
    // dinamik kalitlar
    foreach (\TB\Menu::CORE as $c) {
        $dyn[] = 'menu.' . $c;
    }
    foreach (\TB\Menu::ACTIONS as $a) {
        $dyn[] = 'adm.act_' . $a;
    }
    foreach (\TB\Users::INTERESTS as $i) {
        $dyn[] = 'interest.' . $i;
    }
    for ($r = 1; $r <= \TB\Users::REGIONS; $r++) {
        $dyn[] = 'region.' . $r;
    }
    foreach (\TB\Router::COMMANDS as $c) {
        $dyn[] = 'cmdhelp.' . $c;
    }
    foreach (['f', 'm'] as $a) {
        $dyn[] = 'boost.active_' . $a;
        $dyn[] = 'inv.boost_desc_' . $a;
        $dyn[] = 'pay.boost_ok_' . $a;
        $dyn[] = 'gender.' . $a;
    }
    foreach (['uz', 'ru', 'en'] as $l) {
        $dyn[] = 'adm.bc_prompt_' . $l;
    }
    foreach (['label', 'duplicate'] as $e) {
        $dyn[] = 'adm.menu_label_' . $e;
    }
    foreach (['generic', 'order', 'amount', 'expired', 'profile'] as $e) {
        $dyn[] = 'pay.err_' . $e;
    }
    foreach (\TB\Users::GOALS as $g) {
        $dyn[] = 'goal.' . $g;
    }
    foreach (\TB\Settings::LIKEMSG_MODES as $m) {
        $dyn[] = 'adm.lm_mode_' . $m;
    }
    foreach ([1, 2, 3] as $r) {
        $dyn[] = 'verify.r' . $r;
    }
    foreach ($dyn as $k) {
        if (!isset($keys[$k])) {
            $missing[] = 'dyn:' . $k;
        }
    }
    T::eq($missing, [], 'yetishmagan kalitlar');
    T::eq(Users::REGIONS, 13, '13 hudud');
});
