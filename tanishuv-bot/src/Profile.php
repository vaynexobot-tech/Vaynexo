<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

final class Profile
{
    public static function cardText(string $lang, array $u, bool $own = false): string
    {
        $prem = Users::isPremium($u) ? '💎 ' : '';
        $ints = array_map(static fn($k) => Lang::t($lang, 'interest.' . $k), Users::interests($u));
        $age = Users::age($u);
        $ver = (int)($u['verified'] ?? 0) === 1 ? ' ✅' : '';
        $lines = [
            $prem . (string)$u['name'] . ($age !== null ? ', ' . $age : '') . $ver,
            Lang::t($lang, 'gender.' . ($u['gender'] ?? 'm')) . ' · ' . Lang::t($lang, 'region.' . (int)($u['region'] ?? 1)),
        ];
        if (in_array($u['goal'] ?? null, Users::GOALS, true)) {
            $lines[] = Lang::t($lang, 'goal.' . $u['goal']);
        }
        $lines[] = '❤️ ' . implode(', ', $ints);
        $n = count(Users::photos($u));
        if ($n > 1) {
            $lines[] = '📷 ' . $n;
        }
        if ($own && Users::isPremium($u)) {
            $lines[] = Lang::t($lang, 'premium.until', ['date' => substr((string)$u['premium_until'], 0, 16) . ' UTC']);
        }
        return implode("\n", $lines);
    }

    public static function sendCard(Ctx $ctx, array $u, ?array $markup, bool $own = false, ?int $chat = null, ?string $extra = null): void
    {
        $photos = Users::photos($u);
        $cap = self::cardText($ctx->lang, $u, $own) . ($extra !== null ? "\n\n" . $extra : '');
        $p = ['chat_id' => $chat ?? $ctx->uid, 'caption' => mb_substr($cap, 0, 1000), 'protect_content' => true];
        if ($markup) {
            $p['reply_markup'] = $markup;
        }
        if ($photos) {
            $p['photo'] = $photos[0];
            $ctx->api('sendPhoto', $p, $chat);
        } else {
            $p['text'] = $p['caption'];
            unset($p['caption']);
            $ctx->api('sendMessage', $p, $chat);
        }
    }

    public static function menu(Ctx $ctx, bool $edit = false): void
    {
        $rows = [
            [[$ctx->t('profile.mine'), 'pr:my']],
            [[$ctx->t('profile.saved'), 'pr:sv']],
        ];
        if (Settings::on('verify_enabled') && (int)($ctx->u['verified'] ?? 0) !== 1) {
            $rows[] = [[$ctx->t('verify.btn'), 'pr:vf']];
        }
        $rows[] = [[$ctx->t('btn.back'), 'm:home']];
        $kb = Kb::inline($rows);
        $edit ? $ctx->edit($ctx->t('profile.title'), $kb) : $ctx->send($ctx->t('profile.title'), $kb);
    }

    public static function showMine(Ctx $ctx): void
    {
        self::sendCard($ctx, $ctx->u, Kb::inline([
            [[$ctx->t('profile.settings'), 'pr:set']],
            [[$ctx->t('btn.back'), 'pr:back']],
        ]), true);
    }

    public static function settingsMenu(Ctx $ctx): void
    {
        $review = !Users::isComplete($ctx->u);
        $ctx->send($ctx->t('profile.settings_title'), Kb::inline([
            [[$ctx->t('edit.name'), 'pr:e:name'], [$ctx->t('edit.photo'), 'pr:e:photo']],
            [[$ctx->t('edit.age'), 'pr:e:age'], [$ctx->t('edit.goal'), 'pr:e:goal']],
            [[$ctx->t('edit.gender'), 'pr:e:gender'], [$ctx->t('edit.region'), 'pr:e:region']],
            [[$ctx->t('edit.interests'), 'pr:e:int']],
            [[$ctx->t('btn.back'), $review ? 'pr:rv' : 'pr:my']],
        ]));
    }

    private static function afterEdit(Ctx $ctx): void
    {
        if (!Users::isComplete($ctx->u)) {
            Registration::showReview($ctx);
        } else {
            self::showMine($ctx);
        }
    }

    public static function callback(Ctx $ctx, array $p): void
    {
        $review = !Users::isComplete($ctx->u);
        $pfx = $p[0];
        $a = $p[1] ?? '';
        if ($review && $pfx === 'pr' && !in_array($a, ['set', 'e', 'rv'], true)) {
            $ctx->answer($ctx->t('err.finish_reg'), true);
            return;
        }
        if ($pfx === 'pr') {
            switch ($a) {
                case 'my':
                    $ctx->answer();
                    self::showMine($ctx);
                    return;
                case 'sv':
                    $ctx->answer();
                    Search::startList($ctx, 'sv');
                    return;
                case 'back':
                    $ctx->answer();
                    self::menu($ctx);
                    return;
                case 'set':
                    $ctx->answer();
                    self::settingsMenu($ctx);
                    return;
                case 'rv':
                    $ctx->answer();
                    Registration::showReview($ctx);
                    return;
                case 'e':
                    $ctx->answer();
                    self::startEdit($ctx, $p[2] ?? '');
                    return;
                case 'vf':
                    self::startVerify($ctx);
                    return;
                case 'vx':
                    if (($ctx->u['state'] ?? '') === 'verify') {
                        $ctx->setState(null);
                    }
                    $ctx->answer();
                    $ctx->edit($ctx->t('edit.cancelled'));
                    return;
            }
            $ctx->answer($ctx->t('err.stale'));
            return;
        }
        // e:* — tahrir ichidagi tugmalar; faqat mos holatda ishlaydi
        $state = (string)($ctx->u['state'] ?? '');
        $v = $p[2] ?? '';
        if ($a === 'x') {
            $ctx->setState(null);
            $ctx->answer($ctx->t('edit.cancelled'));
            $ctx->send($ctx->t('edit.cancelled'));
            self::afterEdit($ctx);
            return;
        }
        $need = ['gl' => 'edit:goal', 'g' => 'edit:gender', 'r' => 'edit:region', 'i' => 'edit:int', 'ph' => 'edit:photo'][$a] ?? null;
        if ($need === null || $state !== $need) {
            $ctx->answer($ctx->t('err.stale'));
            return;
        }
        switch ($a) {
            case 'gl':
                if (!in_array($v, Users::GOALS, true)) {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $ctx->set(['goal' => $v, 'state' => null, 'state_data' => null]);
                break;
            case 'g':
                if (!in_array($v, ['m', 'f'], true)) {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $ctx->set(['gender' => $v, 'state' => null, 'state_data' => null]);
                break;
            case 'r':
                $r = ctype_digit($v) ? (int)$v : 0;
                if ($r < 1 || $r > Users::REGIONS) {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $ctx->set(['region' => $r, 'state' => null, 'state_data' => null]);
                break;
            case 'i':
                $sel = array_values(array_intersect((array)($ctx->stateData()['sel'] ?? []), Users::INTERESTS));
                if ($v === 'save') {
                    if (!$sel) {
                        $ctx->answer($ctx->t('err.need_interest'), true);
                        return;
                    }
                    $ctx->set(['interests' => implode(',', $sel), 'state' => null, 'state_data' => null]);
                    break;
                }
                if (!in_array($v, Users::INTERESTS, true)) {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $sel = in_array($v, $sel, true) ? array_values(array_diff($sel, [$v])) : array_merge($sel, [$v]);
                $ctx->setState('edit:int', ['sel' => $sel]);
                $ctx->answer();
                $ctx->edit($ctx->t('edit.interests_prompt'), Registration::interestsKb($ctx, $sel, 'e:i:', 'e:i:save', $ctx->t('btn.save'), 'e:x'));
                return;
            case 'ph':
                if ($v !== 'save') {
                    $ctx->answer($ctx->t('err.stale'));
                    return;
                }
                $draft = array_values(array_filter((array)($ctx->stateData()['draft'] ?? []), 'is_string'));
                if (!$draft) {
                    $ctx->answer($ctx->t('err.need_photo'), true);
                    return;
                }
                $ctx->set(['photos' => json_encode(array_slice($draft, 0, Registration::MAX_PHOTOS)), 'state' => null, 'state_data' => null]);
                if ((int)($ctx->u['verified'] ?? 0) === 1) {
                    // Yangi rasmlar tasdiqlangan selfi bilan solishtirilmagan: belgi qayta tekshiriladi
                    $ctx->set(['verified' => 0]);
                    $ctx->answer($ctx->t('edit.saved'));
                    $ctx->send($ctx->t('verify.reset'));
                    self::afterEdit($ctx);
                    return;
                }
                break;
        }
        $ctx->answer($ctx->t('edit.saved'));
        $ctx->send($ctx->t('edit.saved'));
        self::afterEdit($ctx);
    }

    private static function startEdit(Ctx $ctx, string $field): void
    {
        $cancel = [[$ctx->t('btn.cancel'), 'e:x']];
        switch ($field) {
            case 'name':
                $ctx->setState('edit:name');
                $ctx->send($ctx->t('edit.name_prompt'), Kb::inline([$cancel]));
                return;
            case 'photo':
                $ctx->setState('edit:photo', ['draft' => []]);
                $ctx->send($ctx->t('edit.photo_prompt', ['max' => Registration::MAX_PHOTOS]), Kb::inline([$cancel]));
                return;
            case 'age':
                [$min, $max] = Settings::ageRange();
                $ctx->setState('edit:age');
                $ctx->send($ctx->t('edit.age_prompt', ['min' => $min, 'max' => $max]), Kb::inline([$cancel]));
                return;
            case 'goal':
                $ctx->setState('edit:goal');
                $ctx->send($ctx->t('edit.goal_prompt'), Registration::goalKb($ctx, 'e:gl:', null, 'e:x'));
                return;
            case 'gender':
                $ctx->setState('edit:gender');
                $kb = Registration::genderKb($ctx, 'e:g:');
                $kb['inline_keyboard'][] = [['text' => $cancel[0][0], 'callback_data' => 'e:x']];
                $ctx->send($ctx->t('edit.gender_prompt'), $kb);
                return;
            case 'region':
                $ctx->setState('edit:region');
                $ctx->send($ctx->t('edit.region_prompt'), Registration::regionKb($ctx, 'e:r:', 'e:x'));
                return;
            case 'int':
                $sel = Users::interests($ctx->u);
                $ctx->setState('edit:int', ['sel' => $sel]);
                $ctx->send($ctx->t('edit.interests_prompt'), Registration::interestsKb($ctx, $sel, 'e:i:', 'e:i:save', $ctx->t('btn.save'), 'e:x'));
                return;
        }
        $ctx->send($ctx->t('err.stale'));
    }

    public static function input(Ctx $ctx, array $msg): void
    {
        $state = (string)$ctx->u['state'];
        $text = isset($msg['text']) && is_string($msg['text']) ? $msg['text'] : null;
        if ($state === 'edit:name') {
            $name = $text !== null ? Users::validName($text) : null;
            if ($name === null) {
                $ctx->send($ctx->t('err.name'));
                return;
            }
            $ctx->set(['name' => $name, 'state' => null, 'state_data' => null]);
            $ctx->send($ctx->t('edit.saved'));
            self::afterEdit($ctx);
            return;
        }
        if ($state === 'edit:age') {
            $a = Registration::parseAge($text);
            [$min, $max] = Settings::ageRange();
            if (!is_int($a)) {
                $ctx->send($ctx->t('err.age', ['min' => $min, 'max' => $max]), Kb::inline([[[$ctx->t('btn.cancel'), 'e:x']]]));
                return;
            }
            $ctx->set(['age' => $a, 'state' => null, 'state_data' => null]);
            $ctx->send($ctx->t('edit.saved'));
            self::afterEdit($ctx);
            return;
        }
        if ($state === 'edit:photo') {
            $fid = Registration::photoId($msg);
            $kb = Kb::inline([[[$ctx->t('btn.save'), 'e:ph:save'], [$ctx->t('btn.cancel'), 'e:x']]]);
            if ($fid === null) {
                $ctx->send($ctx->t('err.need_photo'), $kb);
                return;
            }
            $draft = array_values(array_filter((array)($ctx->stateData()['draft'] ?? []), 'is_string'));
            if (count($draft) >= Registration::MAX_PHOTOS) {
                $ctx->send($ctx->t('err.photo_max', ['max' => Registration::MAX_PHOTOS]), $kb);
                return;
            }
            $draft[] = $fid;
            $ctx->setState('edit:photo', ['draft' => $draft]);
            $ctx->send($ctx->t('edit.photo_got', ['n' => count($draft), 'max' => Registration::MAX_PHOTOS]), $kb);
            return;
        }
        $ctx->send($ctx->t('menu.use_buttons'));
    }

    public const GESTURES = ['✌️', '👍', '👌', '🤙', '✋', '🤘'];

    private static function startVerify(Ctx $ctx): void
    {
        if (!Settings::on('verify_enabled')) {
            $ctx->answer($ctx->t('verify.disabled'), true);
            return;
        }
        if ((int)($ctx->u['verified'] ?? 0) === 1) {
            $ctx->answer($ctx->t('verify.already'), true);
            return;
        }
        $pending = App::db()->val("SELECT id FROM tb_verifications WHERE user_id = ? AND status = 'pending' LIMIT 1", [$ctx->uid]);
        if ($pending !== null) {
            $ctx->answer($ctx->t('verify.pending'), true);
            return;
        }
        $g = self::GESTURES[random_int(0, count(self::GESTURES) - 1)];
        $ctx->setState('verify', ['g' => $g]);
        $ctx->answer();
        $ctx->send($ctx->t('verify.prompt', ['gesture' => $g]), Kb::inline([[[$ctx->t('btn.cancel'), 'pr:vx']]]));
    }

    public static function verifyInput(Ctx $ctx, array $msg): void
    {
        $g = (string)($ctx->stateData()['g'] ?? '');
        $fid = Registration::photoId($msg);
        if ($fid === null || !in_array($g, self::GESTURES, true)) {
            $ctx->send($ctx->t('verify.need_photo', ['gesture' => $g ?: '✌️']), Kb::inline([[[$ctx->t('btn.cancel'), 'pr:vx']]]));
            return;
        }
        $db = App::db();
        $db->exec(
            "INSERT INTO tb_verifications (user_id, file_id, gesture, status, created_at) VALUES (?, ?, ?, 'pending', UTC_TIMESTAMP())",
            [$ctx->uid, $fid, $g]
        );
        $ctx->setState(null);
        $ctx->send($ctx->t('verify.sent'));
        Admin::notify($ctx, 'admin.verify_new');
    }

    /** Yangi anketa (photo_review yoqilgan bo‘lsa) admin navbatiga tushadi. Adminlarning o‘zi tekshirilmaydi. */
    public static function queueReview(Ctx $ctx): void
    {
        if (!Settings::on('photo_review') || App::isAdmin($ctx->uid)) {
            return;
        }
        $db = App::db();
        if ($db->val("SELECT 1 FROM tb_profile_reviews WHERE user_id = ? AND status = 'pending' LIMIT 1", [$ctx->uid]) !== null) {
            return;
        }
        $db->exec("INSERT INTO tb_profile_reviews (user_id, status, created_at) VALUES (?, 'pending', UTC_TIMESTAMP())", [$ctx->uid]);
        Admin::notify($ctx, 'admin.review_new');
    }

    public static function deleteCb(Ctx $ctx, string $v): void
    {
        if ($v !== 'yes') {
            $ctx->answer();
            $ctx->edit($ctx->t('delete.cancelled'));
            return;
        }
        $ctx->answer();
        $uid = $ctx->uid;
        $lang = $ctx->lang;
        if (!empty($ctx->u['active_chat_id'])) {
            Chat::end($ctx, (int)$ctx->u['active_chat_id'], 'delete', false);
        }
        $db = App::db();
        $db->exec('DELETE FROM tb_reactions WHERE from_id = ? OR to_id = ?', [$uid, $uid]);
        $db->exec('DELETE FROM tb_seen WHERE viewer_id = ? OR target_id = ?', [$uid, $uid]);
        $db->exec('DELETE FROM tb_matches WHERE user_a = ? OR user_b = ?', [$uid, $uid]);
        $db->exec('DELETE FROM tb_daily_limits WHERE user_id = ?', [$uid]);
        $db->exec('DELETE FROM tb_reg_msgs WHERE user_id = ?', [$uid]);
        $db->exec('DELETE FROM tb_user_ext WHERE user_id = ?', [$uid]);
        $db->exec('DELETE FROM tb_verifications WHERE user_id = ?', [$uid]);
        $db->exec('DELETE FROM tb_blocks WHERE blocker_id = ? OR blocked_id = ?', [$uid, $uid]);
        $db->exec('DELETE FROM tb_referrals WHERE invited_id = ? OR inviter_id = ?', [$uid, $uid]);
        $db->exec('DELETE FROM tb_notices WHERE user_id = ?', [$uid]);
        $db->exec('DELETE FROM tb_profile_reviews WHERE user_id = ?', [$uid]);
        $db->exec('DELETE FROM tb_like_msgs WHERE from_id = ? OR to_id = ?', [$uid, $uid]);
        $db->exec('UPDATE tb_users SET card_target = NULL, card_nonce = NULL WHERE card_target = ?', [$uid]);
        $db->exec('DELETE FROM tb_users WHERE id = ?', [$uid]);
        $ctx->send(Lang::t($lang, 'delete.done'), Kb::remove());
    }
}
