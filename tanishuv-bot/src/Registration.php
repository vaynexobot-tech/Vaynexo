<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * /start ro‘yxatdan o‘tish oqimi. Har bosqich tb_users.reg_step da saqlanadi.
 * Bosqich callbacklari faqat aynan o‘sha bosqichda qabul qilinadi (soxta callback bilan
 * 18+ bosqichini chetlab o‘tib bo‘lmaydi).
 */
final class Registration
{
    public const STEPS = ['lang', 'age', 'agenum', 'name', 'photo', 'gender', 'goal', 'region', 'interests', 'review', 'done'];
    public const MAX_PHOTOS = 5;

    public static function askLang(Ctx $ctx, bool $change = false): void
    {
        $ctx->send(Lang::t('uz', 'lang.choose'), Kb::inline([
            [['🇺🇿 O‘zbekcha', 'lang:uz']],
            [['🇷🇺 Русский', 'lang:ru']],
            [['🇬🇧 English', 'lang:en']],
        ]));
    }

    public static function langCb(Ctx $ctx, string $code): void
    {
        if (!in_array($code, Lang::LANGS, true)) {
            $ctx->answer($ctx->t('err.stale'));
            return;
        }
        $ctx->set(['lang' => $code]);
        $ctx->answer($ctx->t('lang.set'));
        if (($ctx->u['reg_step'] ?? 'lang') === 'lang') {
            $ctx->set(['reg_step' => 'age']);
            self::resume($ctx);
            return;
        }
        if (Users::isComplete($ctx->u)) {
            Menu::home($ctx, 'lang.changed');
            return;
        }
        self::resume($ctx);
    }

    public static function resume(Ctx $ctx): void
    {
        switch ($ctx->u['reg_step'] ?? 'lang') {
            case 'lang':
                self::askLang($ctx);
                return;
            case 'age':
                $ctx->send($ctx->t('reg.age'), Kb::inline([
                    [[$ctx->t('reg.age_yes'), 'reg:age:yes']],
                    [[$ctx->t('reg.age_no'), 'reg:age:no']],
                ]));
                return;
            case 'agenum':
                [$min, $max] = Settings::ageRange();
                $ctx->send($ctx->t('reg.agenum', ['min' => $min, 'max' => $max]), Kb::remove());
                return;
            case 'name':
                $ctx->send($ctx->t('reg.name'), Kb::remove());
                return;
            case 'photo':
                self::askPhoto($ctx);
                return;
            case 'gender':
                $ctx->send($ctx->t('reg.gender'), self::genderKb($ctx, 'reg:g:'));
                return;
            case 'goal':
                $ctx->send($ctx->t('reg.goal'), self::goalKb($ctx, 'reg:gl:'));
                return;
            case 'region':
                $ctx->send($ctx->t('reg.region'), self::regionKb($ctx, 'reg:r:'));
                return;
            case 'interests':
                $ctx->send($ctx->t('reg.interests'), self::interestsKb($ctx, Users::interests($ctx->u), 'reg:i:', 'reg:i:done', $ctx->t('btn.continue')));
                return;
            case 'review':
                self::showReview($ctx);
                return;
            default:
                Menu::home($ctx);
        }
    }

    public static function genderKb(Ctx $ctx, string $pfx): array
    {
        return Kb::inline([[[$ctx->t('gender.m'), $pfx . 'm'], [$ctx->t('gender.f'), $pfx . 'f']]]);
    }

    public static function goalKb(Ctx $ctx, string $pfx, ?string $any = null, ?string $back = null): array
    {
        $rows = [];
        foreach (Users::GOALS as $g) {
            $rows[] = [[$ctx->t('goal.' . $g), $pfx . $g]];
        }
        if ($any !== null) {
            $rows[] = [[$ctx->t('search.any'), $any]];
        }
        if ($back !== null) {
            $rows[] = [[$ctx->t('btn.cancel'), $back]];
        }
        return Kb::inline($rows);
    }

    /**
     * Matndan yoshni o‘qiydi. null = raqam emas; 'under' = 18 dan kichik; 'range' = admin chegarasidan tashqari.
     */
    public static function parseAge(?string $text)
    {
        $t = trim((string)$text);
        if (!preg_match('/^\d{1,3}$/', $t)) {
            return null;
        }
        $n = (int)$t;
        if ($n < 18) {
            return 'under';
        }
        [$min, $max] = Settings::ageRange();
        return ($n < $min || $n > $max) ? 'range' : $n;
    }

    public static function regionKb(Ctx $ctx, string $pfx, ?string $back = null): array
    {
        $rows = [];
        for ($i = 1; $i <= Users::REGIONS; $i += 2) {
            $row = [[$ctx->t('region.' . $i), $pfx . $i]];
            if ($i + 1 <= Users::REGIONS) {
                $row[] = [$ctx->t('region.' . ($i + 1)), $pfx . ($i + 1)];
            }
            $rows[] = $row;
        }
        if ($back) {
            $rows[] = [[$ctx->t('btn.cancel'), $back]];
        }
        return Kb::inline($rows);
    }

    public static function interestsKb(Ctx $ctx, array $sel, string $pfx, string $done, string $doneLabel, ?string $back = null): array
    {
        $rows = [];
        $row = [];
        foreach (Users::INTERESTS as $k) {
            $row[] = [(in_array($k, $sel, true) ? '✅ ' : '') . $ctx->t('interest.' . $k), $pfx . $k];
            if (count($row) === 2) {
                $rows[] = $row;
                $row = [];
            }
        }
        if ($row) {
            $rows[] = $row;
        }
        $rows[] = [[$doneLabel, $done]];
        if ($back) {
            $rows[] = [[$ctx->t('btn.cancel'), $back]];
        }
        return Kb::inline($rows);
    }

    /** Telegram profil rasmini olishga urinadi. Olinmasa faqat "Rasm yuklash" tugmasi. */
    public static function askPhoto(Ctx $ctx): void
    {
        $have = count(Users::photos($ctx->u));
        if ($have > 0) {
            $ctx->send($ctx->t('reg.photo_have', ['n' => $have, 'max' => self::MAX_PHOTOS]), Kb::inline([
                [[$ctx->t('btn.done'), 'reg:ph:done']],
            ]));
            return;
        }
        $fid = self::telegramPhoto($ctx->uid);
        $data = $ctx->stateData();
        if ($fid !== null) {
            $data['tg_photo'] = $fid;
            $ctx->set(['state_data' => json_encode($data)]);
            $ctx->api('sendPhoto', [
                'chat_id' => $ctx->uid,
                'photo' => $fid,
                'caption' => $ctx->t('reg.photo_tg'),
                'reply_markup' => Kb::inline([
                    [[$ctx->t('reg.photo_use_tg'), 'reg:ph:tg']],
                    [[$ctx->t('reg.photo_upload'), 'reg:ph:up']],
                ]),
            ]);
            return;
        }
        unset($data['tg_photo']);
        $ctx->set(['state_data' => $data ? json_encode($data) : null]);
        $ctx->send($ctx->t('reg.photo_none'), Kb::inline([
            [[$ctx->t('reg.photo_upload'), 'reg:ph:up']],
        ]));
    }

    public static function telegramPhoto(int $uid): ?string
    {
        try {
            $r = App::tg()->call('getUserProfilePhotos', ['user_id' => $uid, 'limit' => 1], 5);
        } catch (\Throwable $e) {
            return null;
        }
        $sizes = $r['result']['photos'][0] ?? null;
        if (empty($r['ok']) || !is_array($sizes) || !$sizes) {
            return null;
        }
        $last = end($sizes);
        $fid = is_array($last) ? ($last['file_id'] ?? null) : null;
        return is_string($fid) && $fid !== '' && strlen($fid) <= 255 ? $fid : null;
    }

    public static function photoId(array $msg): ?string
    {
        if (empty($msg['photo']) || !is_array($msg['photo'])) {
            return null;
        }
        $last = end($msg['photo']);
        $fid = is_array($last) ? ($last['file_id'] ?? null) : null;
        return is_string($fid) && $fid !== '' && strlen($fid) <= 255 ? $fid : null;
    }

    public static function message(Ctx $ctx, array $msg): void
    {
        $step = $ctx->u['reg_step'] ?? 'lang';
        $text = isset($msg['text']) && is_string($msg['text']) ? $msg['text'] : null;
        if ($step === 'agenum') {
            $a = self::parseAge($text);
            [$min, $max] = Settings::ageRange();
            if ($a === 'under') {
                $ctx->set(['age_confirmed' => 0, 'reg_step' => 'age']);
                $ctx->send($ctx->t('reg.age_denied'));
                return;
            }
            if (!is_int($a)) {
                $ctx->send($ctx->t('err.age', ['min' => $min, 'max' => $max]));
                return;
            }
            $ctx->set(['age' => $a, 'reg_step' => 'name']);
            self::resume($ctx);
            return;
        }
        if ($step === 'name' && $text !== null) {
            $name = Users::validName($text);
            if ($name === null) {
                $ctx->send($ctx->t('err.name'));
                return;
            }
            $ctx->set(['name' => $name, 'reg_step' => 'photo']);
            self::askPhoto($ctx);
            return;
        }
        if ($step === 'photo' && ($fid = self::photoId($msg)) !== null) {
            $photos = Users::photos($ctx->u);
            if (count($photos) >= self::MAX_PHOTOS) {
                $ctx->send($ctx->t('err.photo_max', ['max' => self::MAX_PHOTOS]), Kb::inline([[[$ctx->t('btn.done'), 'reg:ph:done']]]));
                return;
            }
            $photos[] = $fid;
            $ctx->set(['photos' => json_encode($photos)]);
            $ctx->send($ctx->t('reg.photo_got', ['n' => count($photos), 'max' => self::MAX_PHOTOS]), Kb::inline([[[$ctx->t('btn.done'), 'reg:ph:done']]]));
            return;
        }
        if ($step === 'photo' && $text !== null) {
            $ctx->send($ctx->t('err.need_photo'));
            return;
        }
        self::resume($ctx);
    }

    public static function callback(Ctx $ctx, array $p): void
    {
        $step = $ctx->u['reg_step'] ?? 'lang';
        $what = $p[1] ?? '';
        $val = $p[2] ?? '';
        $expected = ['age' => 'age', 'ph' => 'photo', 'g' => 'gender', 'gl' => 'goal', 'r' => 'region', 'i' => 'interests', 'ok' => 'review', 'edit' => 'review'][$what] ?? null;
        if ($expected === null || $expected !== $step) {
            $ctx->answer($ctx->t('err.stale'));
            self::resume($ctx);
            return;
        }
        switch ($what) {
            case 'age':
                if ($val === 'yes') {
                    $ctx->set(['age_confirmed' => 1, 'reg_step' => 'agenum']);
                    $ctx->answer();
                    self::resume($ctx);
                } else {
                    $ctx->answer($ctx->t('reg.age_denied'), true);
                    $ctx->send($ctx->t('reg.age_denied'));
                }
                return;
            case 'ph':
                if ($val === 'tg') {
                    $fid = $ctx->stateData()['tg_photo'] ?? null;
                    if (!is_string($fid) || $fid === '') {
                        $ctx->answer($ctx->t('err.stale'));
                        self::askPhoto($ctx);
                        return;
                    }
                    $ctx->set(['photos' => json_encode([$fid]), 'reg_step' => 'gender', 'state_data' => null]);
                } elseif ($val === 'up') {
                    $ctx->answer();
                    $ctx->send($ctx->t('reg.photo_send', ['max' => self::MAX_PHOTOS]));
                    return;
                } elseif ($val === 'done') {
                    if (count(Users::photos($ctx->u)) < 1) {
                        $ctx->answer($ctx->t('err.need_photo'), true);
                        return;
                    }
                    $ctx->set(['reg_step' => 'gender', 'state_data' => null]);
                } else {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $ctx->answer();
                self::resume($ctx);
                return;
            case 'g':
                if (!in_array($val, ['m', 'f'], true)) {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $ctx->set(['gender' => $val, 'reg_step' => 'goal']);
                $ctx->answer();
                self::resume($ctx);
                return;
            case 'gl':
                if (!in_array($val, Users::GOALS, true)) {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $ctx->set(['goal' => $val, 'reg_step' => 'region']);
                $ctx->answer();
                self::resume($ctx);
                return;
            case 'r':
                $r = ctype_digit($val) ? (int)$val : 0;
                if ($r < 1 || $r > Users::REGIONS) {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $ctx->set(['region' => $r, 'reg_step' => 'interests']);
                $ctx->answer();
                self::resume($ctx);
                return;
            case 'i':
                $sel = Users::interests($ctx->u);
                if ($val === 'done') {
                    if (!$sel) {
                        $ctx->answer($ctx->t('err.need_interest'), true);
                        return;
                    }
                    $ctx->set(['reg_step' => 'review']);
                    $ctx->answer();
                    self::resume($ctx);
                    return;
                }
                if (!in_array($val, Users::INTERESTS, true)) {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $sel = in_array($val, $sel, true) ? array_values(array_diff($sel, [$val])) : array_merge($sel, [$val]);
                $ctx->set(['interests' => implode(',', $sel)]);
                $ctx->answer();
                $ctx->edit($ctx->t('reg.interests'), self::interestsKb($ctx, $sel, 'reg:i:', 'reg:i:done', $ctx->t('btn.continue')));
                return;
            case 'ok':
                $missing = self::firstMissing($ctx->u);
                if ($missing !== null) {
                    $ctx->set(['reg_step' => $missing]);
                    $ctx->answer($ctx->t('err.stale'));
                    self::resume($ctx);
                    return;
                }
                $ctx->set(['reg_step' => 'done', 'state' => null, 'state_data' => null]);
                $ctx->answer();
                Referrals::reward($ctx);
                Profile::queueReview($ctx);
                RegCleanup::purge($ctx);
                Menu::home($ctx, 'reg.done');
                return;
            case 'edit':
                $ctx->answer();
                Profile::settingsMenu($ctx);
                return;
        }
    }

    /** Profil to‘liqligini qayta tekshiradi; yetishmagan birinchi bosqichni qaytaradi. */
    public static function firstMissing(array $u): ?string
    {
        if (!in_array($u['lang'] ?? null, Lang::LANGS, true)) {
            return 'lang';
        }
        if ((int)($u['age_confirmed'] ?? 0) !== 1) {
            return 'age';
        }
        $age = Users::age($u);
        if ($age === null || $age < 18 || $age > 99) {
            return 'agenum';
        }
        if (Users::validName((string)($u['name'] ?? '')) === null) {
            return 'name';
        }
        $n = count(Users::photos($u));
        if ($n < 1 || $n > self::MAX_PHOTOS) {
            return 'photo';
        }
        if (!in_array($u['gender'] ?? null, ['m', 'f'], true)) {
            return 'gender';
        }
        if (!in_array($u['goal'] ?? null, Users::GOALS, true)) {
            return 'goal';
        }
        $r = (int)($u['region'] ?? 0);
        if ($r < 1 || $r > Users::REGIONS) {
            return 'region';
        }
        if (!Users::interests($u)) {
            return 'interests';
        }
        return null;
    }

    /**
     * Yangilanishdan oldin ro‘yxatdan o‘tgan foydalanuvchida yangi majburiy maydon (yosh, maqsad)
     * bo‘lmasa, uni o‘sha bosqichga qaytaramiz. true = bosqichga qaytarildi.
     */
    public static function upgrade(Ctx $ctx): bool
    {
        if (($ctx->u['reg_step'] ?? '') !== 'done') {
            return false;
        }
        $m = self::firstMissing($ctx->u);
        if ($m === null) {
            return false;
        }
        $ctx->set(['reg_step' => $m]);
        return true;
    }

    public static function showReview(Ctx $ctx): void
    {
        $ctx->send($ctx->t('reg.review'));
        Profile::sendCard($ctx, $ctx->u, Kb::inline([
            [[$ctx->t('btn.confirm'), 'reg:ok']],
            [[$ctx->t('btn.edit'), 'reg:edit']],
        ]), true);
    }
}
