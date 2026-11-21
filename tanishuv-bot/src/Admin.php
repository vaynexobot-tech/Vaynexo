<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Admin panel. Ruxsat /admin kirishda, HAR BIR admin callbackda va HAR BIR keyingi
 * matn kiritish bosqichida config.php dagi admin_ids dan qayta tekshiriladi.
 */
final class Admin
{
    public static function notify(Ctx $ctx, string $key, array $p = []): void
    {
        foreach ((array)App::cfg('admin_ids', []) as $aid) {
            $aid = (int)$aid;
            if ($aid <= 0) {
                continue;
            }
            $u = $aid === $ctx->uid ? $ctx->u : Users::find($aid);
            $l = Lang::norm($u['lang'] ?? null);
            $ctx->api('sendMessage', ['chat_id' => $aid, 'text' => Lang::t($l, $key, $p)], $aid);
        }
    }

    public static function audit(Ctx $ctx, string $action, ?string $target = null, ?string $details = null): void
    {
        App::db()->exec(
            'INSERT INTO tb_admin_audit (admin_id, action, target, details, created_at) VALUES (?, ?, ?, ?, UTC_TIMESTAMP())',
            [$ctx->uid, $action, $target !== null ? mb_substr($target, 0, 128) : null, $details !== null ? mb_substr($details, 0, 500) : null]
        );
    }

    private static function denied(Ctx $ctx): void
    {
        if (str_starts_with((string)($ctx->u['state'] ?? ''), 'adm:')) {
            $ctx->setState(null);
        }
        $ctx->answer($ctx->t('err.no_access'), true);
        $ctx->send($ctx->t('err.no_access'));
    }

    public static function open(Ctx $ctx): void
    {
        if (!App::isAdmin($ctx->uid)) {
            $ctx->send($ctx->t('cmd.unknown'));
            return;
        }
        if (str_starts_with((string)($ctx->u['state'] ?? ''), 'adm:')) {
            $ctx->setState(null);
        }
        self::home($ctx, false);
    }

    public static function home(Ctx $ctx, bool $edit = true): void
    {
        $db = App::db();
        $vq = (int)$db->val("SELECT COUNT(*) FROM tb_verifications WHERE status = 'pending'");
        $lq = (int)$db->val("SELECT COUNT(*) FROM tb_like_msgs WHERE status = 'pending'");
        $hq = (int)$db->val('SELECT COUNT(*) FROM tb_user_ext WHERE mod_hidden = 1');
        $rq = (int)$db->val("SELECT COUNT(*) FROM tb_reports WHERE status = 'open'");
        $pq = (int)$db->val("SELECT COUNT(*) FROM tb_profile_reviews WHERE status = 'pending'");
        $kb = Kb::inline([
            [[$ctx->t('adm.users'), 'a:u:0'], [$ctx->t('adm.reports') . ($rq ? " ($rq)" : ''), 'a:rp:0']],
            [[$ctx->t('adm.verify_q') . " ($vq)", 'a:vq'], [$ctx->t('adm.likemsg_q') . " ($lq)", 'a:lq']],
            [[$ctx->t('adm.hidden_q') . " ($hq)", 'a:hq:0'], [$ctx->t('adm.settings'), 'a:cfg']],
            [[$ctx->t('adm.review_q') . " ($pq)", 'a:pq']],
            [[$ctx->t('adm.premium'), 'a:pm'], [$ctx->t('adm.boost'), 'a:bo']],
            [[$ctx->t('adm.stats'), 'a:st'], [$ctx->t('adm.broadcast'), 'a:bc']],
            [[$ctx->t('adm.menu_edit'), 'a:me'], [$ctx->t('adm.bank'), 'a:bk']],
        ]);
        $edit ? $ctx->edit($ctx->t('adm.title'), $kb) : $ctx->send($ctx->t('adm.title'), $kb);
    }

    private static function back(Ctx $ctx, string $to = 'a:h'): array
    {
        return [[$ctx->t('btn.back'), $to]];
    }

    public static function callback(Ctx $ctx, array $p): void
    {
        if (!App::isAdmin($ctx->uid)) {
            self::denied($ctx);
            return;
        }
        $ctx->answer();
        $a = $p[1] ?? '';
        $arg = $p[2] ?? '';
        $db = App::db();
        if (in_array($a, ['me', 'mi', 'mr', 'mm', 'ma', 'ms', 'mt', 'md', 'mn', 'mp', 'mv', 'mx'], true)) {
            MenuEditor::callback($ctx, $p);
            return;
        }
        if (str_starts_with($a, 'bk')) {
            Bank::adminCallback($ctx, $p);
            return;
        }
        if (in_array($a, ['gc', 'gct', 'gcd', 'gca'], true)) {
            Gate::adminCallback($ctx, $a, $arg);
            return;
        }
        if (str_starts_with($a, 'pp')) {
            P2p::adminCallback($ctx, $a, $arg);
            return;
        }
        switch ($a) {
            case 'h':
                if (str_starts_with((string)($ctx->u['state'] ?? ''), 'adm:')) {
                    $ctx->setState(null);
                }
                self::home($ctx);
                return;
            case 'u':
                self::usersList($ctx, max(0, (int)$arg));
                return;
            case 'uf':
                $ctx->setState('adm:find');
                $ctx->send($ctx->t('adm.find_prompt'), Kb::inline([self::back($ctx, 'a:u:0')]));
                return;
            case 'uv':
                self::userView($ctx, (int)$arg);
                return;
            case 'us':
            case 'ur':
                $uid = (int)$arg;
                $target = Users::find($uid, true);
                if (!$target) {
                    $ctx->send($ctx->t('adm.not_found'));
                    return;
                }
                if ($a === 'us') {
                    $db->exec("UPDATE tb_users SET status = 'suspended' WHERE id = ?", [$uid]);
                    Chat::endForUser($ctx, $uid);
                    self::audit($ctx, 'user.suspend', (string)$uid);
                } else {
                    $db->exec("UPDATE tb_users SET status = 'active' WHERE id = ?", [$uid]);
                    self::audit($ctx, 'user.restore', (string)$uid);
                }
                if ($uid === $ctx->uid) {
                    $ctx->u['status'] = $a === 'us' ? 'suspended' : 'active';
                }
                self::userView($ctx, $uid);
                return;
            case 'rp':
                self::reports($ctx, max(0, (int)$arg));
                return;
            case 'vq':
                self::verifyQueue($ctx);
                return;
            case 'pq':
                self::reviewQueue($ctx);
                return;
            case 'pa':
            case 'ph':
                self::reviewDecide($ctx, $a === 'pa', (int)$arg);
                return;
            case 'va':
            case 'vr':
                self::verifyDecide($ctx, $a === 'va', (int)$arg, (string)($p[3] ?? '1'));
                return;
            case 'lq':
                self::likeMsgQueue($ctx);
                return;
            case 'la':
            case 'lr':
                self::likeMsgDecide($ctx, $a === 'la', (int)$arg);
                return;
            case 'hq':
                self::hiddenList($ctx, max(0, (int)$arg));
                return;
            case 'uh':
            case 'uhd':
            case 'uvf':
            case 'uvu':
                $uid = (int)$arg;
                if (!Users::find($uid)) {
                    $ctx->send($ctx->t('adm.not_found'));
                    return;
                }
                $map = ['uh' => ['mod_hidden', 0, 'user.unhide'], 'uhd' => ['mod_hidden', 1, 'user.hide'], 'uvf' => ['verified', 1, 'user.verify'], 'uvu' => ['verified', 0, 'user.unverify']];
                [$col, $val, $act] = $map[$a];
                Users::updateExt($uid, [$col => $val]);
                if ($uid === $ctx->uid) {
                    $ctx->u[$col] = $val;
                }
                self::audit($ctx, $act, (string)$uid);
                if ($a === 'uvf') {
                    self::tellUser($ctx, $uid, 'verify.approved');
                }
                self::userView($ctx, $uid);
                return;
            case 'ug':
                if (!Users::find((int)$arg)) {
                    $ctx->send($ctx->t('adm.not_found'));
                    return;
                }
                $ctx->setState('adm:grant', ['uid' => (int)$arg]);
                $ctx->send($ctx->t('adm.grant_prompt', ['id' => (int)$arg]), Kb::inline([self::back($ctx, 'a:uv:' . (int)$arg)]));
                return;
            case 'cfg':
                self::settingsView($ctx);
                return;
            case 'cf':
                self::settingsCb($ctx, $arg);
                return;
            case 'rd':
                $n = $db->exec("UPDATE tb_reports SET status = 'reviewed', reviewed_at = UTC_TIMESTAMP(), reviewed_by = ? WHERE id = ? AND status = 'open'", [$ctx->uid, (int)$arg]);
                if ($n) {
                    self::audit($ctx, 'report.reviewed', (string)(int)$arg);
                }
                self::reports($ctx, 0);
                return;
            case 'pm':
                self::productsView($ctx, 'premium');
                return;
            case 'bo':
                self::productsView($ctx, 'boost');
                return;
            case 'pe':
            case 'pd':
                $prod = $db->one('SELECT * FROM tb_products WHERE id = ?', [(int)$arg]);
                if (!$prod) {
                    $ctx->send($ctx->t('adm.not_found'));
                    return;
                }
                $ctx->setState($a === 'pe' ? 'adm:price' : 'adm:days', ['pid' => (int)$prod['id']]);
                $ctx->send($ctx->t($a === 'pe' ? 'adm.price_prompt' : 'adm.days_prompt', ['code' => $prod['code']]), Kb::inline([self::back($ctx, $prod['kind'] === 'premium' ? 'a:pm' : 'a:bo')]));
                return;
            case 'st':
                self::stats($ctx);
                return;
            case 'bc':
                self::broadcasts($ctx);
                return;
            case 'bn':
                $ctx->setState('adm:bc', ['step' => 'uz']);
                $ctx->send($ctx->t('adm.bc_prompt_uz'), Kb::inline([self::back($ctx, 'a:bc')]));
                return;
            case 'by':
                $b = $db->one('SELECT * FROM tb_broadcasts WHERE id = ? FOR UPDATE', [(int)$arg]);
                if (!$b || $b['status'] !== 'draft') {
                    $ctx->send($ctx->t('err.stale'));
                    return;
                }
                $db->exec("UPDATE tb_broadcasts SET status = 'queued', confirmed_at = UTC_TIMESTAMP() WHERE id = ?", [$b['id']]);
                self::audit($ctx, 'broadcast.confirm', (string)$b['id']);
                $ctx->send($ctx->t('adm.bc_queued', ['id' => $b['id']]));
                return;
            case 'bx':
                $n = $db->exec("UPDATE tb_broadcasts SET status = 'cancelled', cancel_reason = 'admin', finished_at = UTC_TIMESTAMP() WHERE id = ? AND status IN ('draft','queued')", [(int)$arg]);
                if ($n) {
                    self::audit($ctx, 'broadcast.cancel', (string)(int)$arg);
                }
                $ctx->send($ctx->t($n ? 'adm.bc_cancelled' : 'err.stale'));
                return;
        }
        $ctx->send($ctx->t('err.stale'));
    }

    public static function input(Ctx $ctx, array $msg): void
    {
        if (!App::isAdmin($ctx->uid)) {
            self::denied($ctx);
            return;
        }
        $state = (string)$ctx->u['state'];
        $text = isset($msg['text']) && is_string($msg['text']) ? trim($msg['text']) : null;
        if ($text === null || $text === '') {
            $ctx->send($ctx->t('adm.need_text'));
            return;
        }
        $d = $ctx->stateData();
        $db = App::db();
        switch ($state) {
            case 'adm:find':
                if (!ctype_digit($text) || strlen($text) > 15) {
                    $ctx->send($ctx->t('adm.bad_number'));
                    return;
                }
                $ctx->setState(null);
                self::userView($ctx, (int)$text);
                return;
            case 'adm:price':
            case 'adm:days':
                $max = $state === 'adm:price' ? 100000 : 365;
                if (!ctype_digit($text) || (int)$text < 1 || (int)$text > $max) {
                    $ctx->send($ctx->t('adm.bad_range', ['min' => 1, 'max' => $max]));
                    return;
                }
                $prod = $db->one('SELECT * FROM tb_products WHERE id = ? FOR UPDATE', [(int)($d['pid'] ?? 0)]);
                if (!$prod) {
                    $ctx->setState(null);
                    $ctx->send($ctx->t('adm.not_found'));
                    return;
                }
                $col = $state === 'adm:price' ? 'price_xtr' : 'days';
                $db->exec("UPDATE tb_products SET $col = ?, updated_at = UTC_TIMESTAMP() WHERE id = ?", [(int)$text, $prod['id']]);
                self::audit($ctx, 'product.' . $col, (string)$prod['code'], $prod[$col] . ' -> ' . (int)$text);
                $ctx->setState(null);
                $ctx->send($ctx->t('adm.saved'));
                self::productsView($ctx, (string)$prod['kind'], false);
                return;
            case 'adm:grant':
                if (!ctype_digit($text) || (int)$text < 1 || (int)$text > 365) {
                    $ctx->send($ctx->t('adm.bad_range', ['min' => 1, 'max' => 365]));
                    return;
                }
                $uid = (int)($d['uid'] ?? 0);
                $days = (int)$text;
                $n = $db->exec(
                    'UPDATE tb_users SET premium_until = GREATEST(COALESCE(premium_until, UTC_TIMESTAMP()), UTC_TIMESTAMP()) + INTERVAL ? DAY WHERE id = ?',
                    [$days, $uid]
                );
                $ctx->setState(null);
                if (!$n) {
                    $ctx->send($ctx->t('adm.not_found'));
                    return;
                }
                self::audit($ctx, 'user.grant_premium', (string)$uid, $days . 'd');
                $until = (string)$db->val('SELECT premium_until FROM tb_users WHERE id = ?', [$uid]);
                if ($uid === $ctx->uid) {
                    $ctx->u['premium_until'] = $until;
                }
                self::tellUser($ctx, $uid, 'premium.granted', ['date' => substr($until, 0, 16) . ' UTC']);
                $ctx->send($ctx->t('adm.saved'));
                self::userView($ctx, $uid);
                return;
            case 'adm:cfage':
                if (!preg_match('/^(\d{2})\s+(\d{2})$/', $text, $m) || (int)$m[1] < 18 || (int)$m[2] > 99 || (int)$m[1] > (int)$m[2]) {
                    $ctx->send($ctx->t('adm.cf_age_bad'));
                    return;
                }
                Settings::set('age_min', (string)(int)$m[1]);
                Settings::set('age_max', (string)(int)$m[2]);
                self::audit($ctx, 'settings.age', null, $m[1] . '-' . $m[2]);
                $ctx->setState(null);
                self::settingsView($ctx, false);
                return;
            case 'adm:cfah':
                if (!preg_match('/^(\d{1,2})\s+(\d{1,3})$/', $text, $m) || (int)$m[1] > 50 || (int)$m[2] < 1 || (int)$m[2] > 365) {
                    $ctx->send($ctx->t('adm.cf_ah_bad'));
                    return;
                }
                Settings::set('autohide_reports', (string)(int)$m[1]);
                Settings::set('autohide_days', (string)(int)$m[2]);
                self::audit($ctx, 'settings.autohide', null, $m[1] . '/' . $m[2]);
                $ctx->setState(null);
                self::settingsView($ctx, false);
                return;
            case 'adm:cfsw':
                if (mb_strlen($text) > 3000) {
                    $ctx->send($ctx->t('adm.bad_length', ['max' => 3000]));
                    return;
                }
                Settings::set('likemsg_stopwords', $text === '-' ? '' : $text);
                self::audit($ctx, 'settings.stopwords', null, (string)count(Settings::stopwords()));
                $ctx->setState(null);
                self::settingsView($ctx, false);
                return;
            case 'adm:bc':
                if (mb_strlen($text) > 3500) {
                    $ctx->send($ctx->t('adm.bad_length', ['max' => 3500]));
                    return;
                }
                $step = $d['step'] ?? 'uz';
                $d[$step] = $text;
                if ($step === 'uz' || $step === 'ru') {
                    $next = $step === 'uz' ? 'ru' : 'en';
                    $d['step'] = $next;
                    $ctx->setState('adm:bc', $d);
                    $ctx->send($ctx->t('adm.bc_prompt_' . $next), Kb::inline([self::back($ctx, 'a:bc')]));
                    return;
                }
                $db->exec(
                    "INSERT INTO tb_broadcasts (admin_id, text_uz, text_ru, text_en, status, created_at) VALUES (?, ?, ?, ?, 'draft', UTC_TIMESTAMP())",
                    [$ctx->uid, (string)$d['uz'], (string)$d['ru'], (string)$d['en']]
                );
                $bid = $db->lastId();
                self::audit($ctx, 'broadcast.create', (string)$bid);
                $ctx->setState(null);
                foreach (Lang::LANGS as $l) {
                    $ctx->send('👁 ' . strtoupper($l) . ":\n\n" . (string)$d[$l]);
                }
                $ctx->send($ctx->t('adm.bc_confirm', ['id' => $bid]), Kb::inline([
                    [[$ctx->t('btn.confirm'), 'a:by:' . $bid], [$ctx->t('btn.cancel'), 'a:bx:' . $bid]],
                ]));
                return;
        }
        if (str_starts_with($state, 'adm:m')) {
            MenuEditor::input($ctx, $text);
            return;
        }
        if ($state === 'adm:gch') {
            Gate::adminInput($ctx, $text);
            return;
        }
        if (str_starts_with($state, 'adm:p2p')) {
            P2p::adminInput($ctx, $state, $text);
            return;
        }
        if (in_array($state, ['adm:card', 'adm:pend'], true)) {
            Bank::adminInput($ctx, $text);
            return;
        }
        $ctx->setState(null);
        self::home($ctx, false);
    }

    private static function usersList(Ctx $ctx, int $page): void
    {
        $db = App::db();
        $per = 10;
        $total = (int)$db->val('SELECT COUNT(*) FROM tb_users');
        $off = $page * $per;
        $rows = $db->all("SELECT id, name, status, reg_step FROM tb_users ORDER BY created_at DESC, id DESC LIMIT $per OFFSET $off");
        $kb = [];
        foreach ($rows as $r) {
            $flag = $r['status'] === 'suspended' ? '⛔' : ($r['reg_step'] === 'done' ? '✅' : '⏳');
            $kb[] = [[$flag . ' ' . $r['id'] . ' · ' . mb_substr((string)($r['name'] ?? '—'), 0, 20), 'a:uv:' . $r['id']]];
        }
        $nav = [];
        if ($page > 0) {
            $nav[] = ['⬅️', 'a:u:' . ($page - 1)];
        }
        if ($off + $per < $total) {
            $nav[] = ['➡️', 'a:u:' . ($page + 1)];
        }
        if ($nav) {
            $kb[] = $nav;
        }
        $kb[] = [[$ctx->t('adm.find'), 'a:uf']];
        $kb[] = self::back($ctx);
        $pages = max(1, (int)ceil($total / $per));
        $ctx->edit($ctx->t('adm.users_title', ['total' => $total, 'page' => $page + 1, 'pages' => $pages]), Kb::inline($kb));
    }

    private static function userView(Ctx $ctx, int $uid): void
    {
        $u = Users::find($uid);
        if (!$u) {
            $ctx->send($ctx->t('adm.not_found'), Kb::inline([self::back($ctx, 'a:u:0')]));
            return;
        }
        $db = App::db();
        $txt = $ctx->t('adm.user_card', [
            'id' => $u['id'],
            'name' => (string)($u['name'] ?? '—'),
            'status' => $u['status'],
            'reg' => $u['reg_step'],
            'premium' => Users::isPremium($u) ? substr((string)$u['premium_until'], 0, 16) . ' UTC' : '—',
            'created' => substr((string)$u['created_at'], 0, 16),
        ]);
        $txt .= "\n" . $ctx->t('adm.user_more', [
            'age' => Users::age($u) ?? '—',
            'goal' => in_array($u['goal'] ?? null, Users::GOALS, true) ? $ctx->t('goal.' . $u['goal']) : '—',
            'verified' => (int)$u['verified'] === 1 ? '✅' : '—',
            'hidden' => (int)$u['mod_hidden'] === 1 ? '🙈' : '—',
            'reports' => (int)$db->val('SELECT COUNT(*) FROM tb_reports WHERE reported_id = ?', [$uid]),
            'likes' => (int)$db->val("SELECT COUNT(*) FROM tb_reactions WHERE to_id = ? AND kind IN ('like','super')", [$uid]),
            'matches' => (int)$db->val('SELECT COUNT(*) FROM tb_matches WHERE user_a = ? OR user_b = ?', [$uid, $uid]),
            'seen' => substr((string)($u['last_seen_at'] ?? ''), 0, 16),
        ]);
        $btn = $u['status'] === 'suspended'
            ? [$ctx->t('adm.restore'), 'a:ur:' . $u['id']]
            : [$ctx->t('adm.suspend'), 'a:us:' . $u['id']];
        $hide = (int)$u['mod_hidden'] === 1 ? [$ctx->t('adm.unhide'), 'a:uh:' . $u['id']] : [$ctx->t('adm.hide'), 'a:uhd:' . $u['id']];
        $ver = (int)$u['verified'] === 1 ? [$ctx->t('adm.unverify'), 'a:uvu:' . $u['id']] : [$ctx->t('adm.verify'), 'a:uvf:' . $u['id']];
        if (Users::photos($u) && Users::isComplete($u)) {
            Profile::sendCard($ctx, $u, null);
        }
        $ctx->send($txt, Kb::inline([
            [$btn, $hide],
            [$ver, [$ctx->t('adm.grant'), 'a:ug:' . $u['id']]],
            self::back($ctx, 'a:u:0'),
        ]));
    }

    /** Foydalanuvchiga o‘z tilida xabar. */
    private static function tellUser(Ctx $ctx, int $uid, string $key, array $p = []): void
    {
        $u = $uid === $ctx->uid ? $ctx->u : Users::find($uid);
        if (!$u) {
            return;
        }
        $l = Lang::norm($u['lang'] ?? null);
        $ctx->api('sendMessage', ['chat_id' => $uid, 'text' => Lang::t($l, $key, $p)], $uid);
    }

    /** Yangi anketalar navbati (photo_review yoqilganda): birinchi rasm + karta, «Yaxshi» yoki «Yashirish». */
    private static function reviewQueue(Ctx $ctx): void
    {
        $db = App::db();
        $v = $db->one("SELECT * FROM tb_profile_reviews WHERE status = 'pending' ORDER BY id ASC LIMIT 1");
        if (!$v) {
            $ctx->send($ctx->t('adm.review_empty'), Kb::inline([self::back($ctx)]));
            return;
        }
        $total = (int)$db->val("SELECT COUNT(*) FROM tb_profile_reviews WHERE status = 'pending'");
        $u = Users::find((int)$v['user_id']);
        $ph = $u ? Users::photos($u) : [];
        if (!$u || !Users::isComplete($u)) {
            $db->exec("UPDATE tb_profile_reviews SET status = 'cancelled', decided_at = UTC_TIMESTAMP() WHERE id = ?", [$v['id']]);
            self::reviewQueue($ctx);
            return;
        }
        $cap = $ctx->t('adm.review_item', ['id' => $v['id'], 'n' => $total, 'uid' => $u['id']]) . "\n\n" . Profile::cardText($ctx->lang, $u);
        $kb = Kb::inline([
            [[$ctx->t('adm.review_ok'), 'a:pa:' . $v['id']], [$ctx->t('adm.review_hide'), 'a:ph:' . $v['id']]],
            [[$ctx->t('adm.view_user'), 'a:uv:' . $u['id']], [$ctx->t('btn.back'), 'a:h']],
        ]);
        if ($ph) {
            $ctx->api('sendPhoto', ['chat_id' => $ctx->uid, 'photo' => $ph[0], 'caption' => mb_substr($cap, 0, 1000), 'protect_content' => true, 'reply_markup' => $kb]);
        } else {
            $ctx->send($cap, $kb);
        }
    }

    private static function reviewDecide(Ctx $ctx, bool $ok, int $id): void
    {
        $db = App::db();
        $v = $db->one('SELECT * FROM tb_profile_reviews WHERE id = ? FOR UPDATE', [$id]);
        if (!$v || $v['status'] !== 'pending') {
            $ctx->send($ctx->t('err.stale'));
            self::reviewQueue($ctx);
            return;
        }
        $uid = (int)$v['user_id'];
        $db->exec(
            "UPDATE tb_profile_reviews SET status = ?, admin_id = ?, decided_at = UTC_TIMESTAMP() WHERE id = ?",
            [$ok ? 'approved' : 'hidden', $ctx->uid, $id]
        );
        if (!$ok) {
            Users::updateExt($uid, ['mod_hidden' => 1]);
        }
        $action = $ok ? 'review_approve' : 'review_hide';
        self::audit($ctx, $action, (string)$uid, '#' . $id);
        $ctx->send($ctx->t($ok ? 'adm.review_done_ok' : 'adm.review_done_hide', ['id' => $id]));
        self::reviewQueue($ctx);
    }

    private static function verifyQueue(Ctx $ctx): void
    {
        $db = App::db();
        $v = $db->one("SELECT * FROM tb_verifications WHERE status = 'pending' ORDER BY id ASC LIMIT 1");
        if (!$v) {
            $ctx->send($ctx->t('adm.verify_empty'), Kb::inline([self::back($ctx)]));
            return;
        }
        $total = (int)$db->val("SELECT COUNT(*) FROM tb_verifications WHERE status = 'pending'");
        $u = Users::find((int)$v['user_id']);
        if (!$u) {
            $db->exec("UPDATE tb_verifications SET status = 'cancelled', decided_at = UTC_TIMESTAMP() WHERE id = ?", [$v['id']]);
            self::verifyQueue($ctx);
            return;
        }
        $cap = $ctx->t('adm.verify_item', ['id' => $v['id'], 'n' => $total, 'uid' => $u['id'], 'gesture' => $v['gesture']])
            . "\n\n" . Profile::cardText($ctx->lang, $u);
        $ctx->api('sendPhoto', [
            'chat_id' => $ctx->uid,
            'photo' => (string)$v['file_id'],
            'caption' => mb_substr($cap, 0, 1000),
            'protect_content' => true,
            'reply_markup' => Kb::inline([
                [[$ctx->t('adm.verify_ok'), 'a:va:' . $v['id']]],
                [[$ctx->t('verify.r1'), 'a:vr:' . $v['id'] . ':1'], [$ctx->t('verify.r2'), 'a:vr:' . $v['id'] . ':2']],
                [[$ctx->t('verify.r3'), 'a:vr:' . $v['id'] . ':3']],
                [[$ctx->t('adm.view_user'), 'a:uv:' . $u['id']], [$ctx->t('btn.back'), 'a:h']],
            ]),
        ]);
        // Solishtirish uchun anketaning birinchi rasmi
        $ph = Users::photos($u);
        if ($ph) {
            $ctx->api('sendPhoto', ['chat_id' => $ctx->uid, 'photo' => $ph[0], 'caption' => $ctx->t('adm.verify_profile_photo'), 'protect_content' => true]);
        }
    }

    private static function verifyDecide(Ctx $ctx, bool $ok, int $id, string $reason): void
    {
        $db = App::db();
        $v = $db->one('SELECT * FROM tb_verifications WHERE id = ? FOR UPDATE', [$id]);
        if (!$v || $v['status'] !== 'pending') {
            $ctx->send($ctx->t('err.stale'));
            self::verifyQueue($ctx);
            return;
        }
        $uid = (int)$v['user_id'];
        if ($ok) {
            $db->exec("UPDATE tb_verifications SET status = 'approved', admin_id = ?, decided_at = UTC_TIMESTAMP() WHERE id = ?", [$ctx->uid, $id]);
            Users::updateExt($uid, ['verified' => 1]);
            if ($uid === $ctx->uid) {
                $ctx->u['verified'] = 1;
            }
            self::audit($ctx, 'verify.approve', (string)$uid, '#' . $id);
            self::tellUser($ctx, $uid, 'verify.approved');
        } else {
            $r = in_array($reason, ['1', '2', '3'], true) ? $reason : '1';
            $db->exec("UPDATE tb_verifications SET status = 'rejected', admin_id = ?, reason = ?, decided_at = UTC_TIMESTAMP() WHERE id = ?", [$ctx->uid, 'r' . $r, $id]);
            self::audit($ctx, 'verify.reject', (string)$uid, '#' . $id . ' r' . $r);
            $u = Users::find($uid);
            $l = Lang::norm($u['lang'] ?? null);
            $ctx->api('sendMessage', ['chat_id' => $uid, 'text' => Lang::t($l, 'verify.rejected', ['reason' => Lang::t($l, 'verify.r' . $r)])], $uid);
        }
        $ctx->send($ctx->t($ok ? 'adm.verify_done_ok' : 'adm.verify_done_no', ['id' => $id]));
        self::verifyQueue($ctx);
    }

    private static function likeMsgQueue(Ctx $ctx): void
    {
        $db = App::db();
        $m = $db->one("SELECT * FROM tb_like_msgs WHERE status = 'pending' ORDER BY id ASC LIMIT 1");
        $mode = Settings::likeMsgMode();
        if (!$m) {
            $recent = $db->all("SELECT * FROM tb_like_msgs ORDER BY id DESC LIMIT 5");
            $lines = [$ctx->t('adm.likemsg_empty', ['mode' => $ctx->t('adm.lm_mode_' . $mode)])];
            foreach ($recent as $r) {
                $lines[] = '#' . $r['id'] . ' · ' . $r['status'] . ' · ' . $r['from_id'] . ' → ' . $r['to_id'] . "\n«" . mb_substr((string)$r['text'], 0, 120) . '»';
            }
            $ctx->send(implode("\n\n", $lines), Kb::inline([[[$ctx->t('adm.settings'), 'a:cfg']], self::back($ctx)]));
            return;
        }
        $total = (int)$db->val("SELECT COUNT(*) FROM tb_like_msgs WHERE status = 'pending'");
        $ctx->send($ctx->t('adm.likemsg_item', ['id' => $m['id'], 'n' => $total, 'from' => $m['from_id'], 'to' => $m['to_id'], 'text' => $m['text']]), Kb::inline([
            [[$ctx->t('adm.lm_approve'), 'a:la:' . $m['id']], [$ctx->t('adm.lm_reject'), 'a:lr:' . $m['id']]],
            [[$ctx->t('adm.view_user'), 'a:uv:' . $m['from_id']], [$ctx->t('adm.suspend'), 'a:us:' . $m['from_id']]],
            self::back($ctx),
        ]));
    }

    private static function likeMsgDecide(Ctx $ctx, bool $ok, int $id): void
    {
        $db = App::db();
        $m = $db->one('SELECT * FROM tb_like_msgs WHERE id = ? FOR UPDATE', [$id]);
        if (!$m || $m['status'] !== 'pending') {
            $ctx->send($ctx->t('err.stale'));
            self::likeMsgQueue($ctx);
            return;
        }
        $db->exec('UPDATE tb_like_msgs SET status = ?, admin_id = ?, decided_at = UTC_TIMESTAMP() WHERE id = ?', [$ok ? 'delivered' : 'rejected', $ctx->uid, $id]);
        self::audit($ctx, 'lmsg_' . ($ok ? 'approve' : 'reject'), (string)$m['from_id'], '#' . $id);
        $to = Users::find((int)$m['to_id']);
        if ($ok && Users::isVisible($to)) {
            $l = Lang::norm($to['lang'] ?? null);
            $ctx->api('sendMessage', [
                'chat_id' => (int)$to['id'],
                'text' => Lang::t($l, 'likemsg.notify', ['text' => (string)$m['text']]),
                'reply_markup' => Kb::inline([[[Lang::t($l, 'likemsg.view'), 'lk:l']]]),
                'protect_content' => true,
            ], (int)$to['id']);
        }
        self::likeMsgQueue($ctx);
    }

    private static function hiddenList(Ctx $ctx, int $page): void
    {
        $db = App::db();
        $per = 10;
        $off = $page * $per;
        $total = (int)$db->val('SELECT COUNT(*) FROM tb_user_ext WHERE mod_hidden = 1');
        $rows = $db->all(
            "SELECT x.user_id, x.hidden_at, u.name, (SELECT COUNT(*) FROM tb_reports r WHERE r.reported_id = x.user_id) AS reps
             FROM tb_user_ext x LEFT JOIN tb_users u ON u.id = x.user_id WHERE x.mod_hidden = 1 ORDER BY x.hidden_at DESC LIMIT $per OFFSET $off"
        );
        $kb = [];
        foreach ($rows as $r) {
            $kb[] = [['🙈 ' . $r['user_id'] . ' · ' . mb_substr((string)($r['name'] ?? '—'), 0, 16) . ' · 🚩' . $r['reps'], 'a:uv:' . $r['user_id']]];
        }
        $nav = [];
        if ($page > 0) {
            $nav[] = ['⬅️', 'a:hq:' . ($page - 1)];
        }
        if ($off + $per < $total) {
            $nav[] = ['➡️', 'a:hq:' . ($page + 1)];
        }
        if ($nav) {
            $kb[] = $nav;
        }
        $kb[] = self::back($ctx);
        $ctx->edit($ctx->t($total ? 'adm.hidden_title' : 'adm.hidden_empty', ['n' => $total]), Kb::inline($kb));
    }

    private static function settingsView(Ctx $ctx, bool $edit = true): void
    {
        [$min, $max] = Settings::ageRange();
        $mode = Settings::likeMsgMode();
        $ah = Settings::int('autohide_reports');
        $txt = $ctx->t('adm.cf_title', [
            'age' => $min . '–' . $max,
            'lm' => $ctx->t('adm.lm_mode_' . $mode),
            'links' => Settings::on('likemsg_links') ? '✅' : '❌',
            'sw' => count(Settings::stopwords()),
            'vf' => Settings::on('verify_enabled') ? '✅' : '❌',
            'ah' => $ah > 0 ? $ctx->t('adm.cf_ah_val', ['n' => $ah, 'd' => Settings::int('autohide_days')]) : '❌',
        ]) . "\n" . $ctx->t('adm.cf_more', [
            'lg' => Settings::on('likes_gate') ? '✅' : '❌',
            'pr' => Settings::on('photo_review') ? '✅' : '❌',
            'rt' => Settings::on('retention') ? '✅' : '❌',
        ]);
        $kb = Kb::inline([
            [[$ctx->t('adm.cf_age'), 'a:cf:age']],
            [[$ctx->t('adm.cf_lm'), 'a:cf:lm'], [$ctx->t('adm.cf_links'), 'a:cf:ln']],
            [[$ctx->t('adm.cf_sw'), 'a:cf:sw']],
            [[$ctx->t('adm.cf_vf'), 'a:cf:vf'], [$ctx->t('adm.cf_ah'), 'a:cf:ah']],
            [[$ctx->t('adm.cf_lg'), 'a:cf:lg'], [$ctx->t('adm.cf_pr'), 'a:cf:pr']],
            [[$ctx->t('adm.cf_rt'), 'a:cf:rt']],
            [[$ctx->t('adm.cf_gate'), 'a:gc'], [$ctx->t('adm.cf_p2p'), 'a:pp']],
            self::back($ctx),
        ]);
        $edit ? $ctx->edit($txt, $kb) : $ctx->send($txt, $kb);
    }

    private static function settingsCb(Ctx $ctx, string $k): void
    {
        $back = Kb::inline([self::back($ctx, 'a:cfg')]);
        switch ($k) {
            case 'age':
                [$min, $max] = Settings::ageRange();
                $ctx->setState('adm:cfage');
                $ctx->send($ctx->t('adm.cf_age_prompt', ['min' => $min, 'max' => $max]), $back);
                return;
            case 'ah':
                $ctx->setState('adm:cfah');
                $ctx->send($ctx->t('adm.cf_ah_prompt'), $back);
                return;
            case 'sw':
                $ctx->setState('adm:cfsw');
                $cur = Settings::stopwords();
                $ctx->send($ctx->t('adm.cf_sw_prompt', ['list' => $cur ? implode(', ', array_slice($cur, 0, 60)) : '—']), $back);
                return;
            case 'lm':
                $modes = Settings::LIKEMSG_MODES;
                $next = $modes[(array_search(Settings::likeMsgMode(), $modes, true) + 1) % count($modes)];
                Settings::set('likemsg_mode', $next);
                self::audit($ctx, 'settings.likemsg_mode', null, $next);
                break;
            case 'ln':
                Settings::set('likemsg_links', Settings::on('likemsg_links') ? '0' : '1');
                self::audit($ctx, 'settings.likemsg_links', null, Settings::get('likemsg_links'));
                break;
            case 'vf':
                Settings::set('verify_enabled', Settings::on('verify_enabled') ? '0' : '1');
                self::audit($ctx, 'settings.verify', null, Settings::get('verify_enabled'));
                break;
            case 'lg':
            case 'pr':
            case 'rt':
                $key = ['lg' => 'likes_gate', 'pr' => 'photo_review', 'rt' => 'retention'][$k];
                Settings::set($key, Settings::on($key) ? '0' : '1');
                self::audit($ctx, 'settings.' . $key, null, Settings::get($key));
                break;
            default:
                $ctx->send($ctx->t('err.stale'));
                return;
        }
        self::settingsView($ctx);
    }

    private static function reports(Ctx $ctx, int $page): void
    {
        $db = App::db();
        $per = 5;
        $off = $page * $per;
        $total = (int)$db->val("SELECT COUNT(*) FROM tb_reports WHERE status = 'open'");
        $rows = $db->all("SELECT * FROM tb_reports WHERE status = 'open' ORDER BY created_at ASC, id ASC LIMIT $per OFFSET $off");
        if (!$rows) {
            $ctx->send($ctx->t('adm.no_reports'), Kb::inline([self::back($ctx)]));
            return;
        }
        $lines = [$ctx->t('adm.reports_title', ['total' => $total])];
        $kb = [];
        foreach ($rows as $r) {
            $lines[] = $ctx->t('adm.report_item', [
                'id' => $r['id'], 'from' => $r['reporter_id'], 'to' => $r['reported_id'],
                'reason' => $r['reason'], 'date' => substr((string)$r['created_at'], 0, 16),
            ]);
            $kb[] = [[$ctx->t('adm.reviewed', ['id' => $r['id']]), 'a:rd:' . $r['id']], [$ctx->t('adm.view_user'), 'a:uv:' . $r['reported_id']]];
        }
        $nav = [];
        if ($page > 0) {
            $nav[] = ['⬅️', 'a:rp:' . ($page - 1)];
        }
        if ($off + $per < $total) {
            $nav[] = ['➡️', 'a:rp:' . ($page + 1)];
        }
        if ($nav) {
            $kb[] = $nav;
        }
        $kb[] = self::back($ctx);
        $ctx->send(implode("\n\n", $lines), Kb::inline($kb));
    }

    private static function productsView(Ctx $ctx, string $kind, bool $edit = true): void
    {
        $rows = App::db()->all('SELECT * FROM tb_products WHERE kind = ? ORDER BY sort, id', [$kind]);
        $kb = [];
        $lines = [$ctx->t($kind === 'premium' ? 'adm.premium_title' : 'adm.boost_title')];
        foreach ($rows as $r) {
            $lines[] = $ctx->t('adm.product_line', ['days' => $r['days'], 'price' => $r['price_xtr']]);
            $kb[] = [[$ctx->t('adm.edit_price', ['days' => $r['days'], 'price' => $r['price_xtr']]), 'a:pe:' . $r['id']]];
            if ($kind === 'boost') {
                $kb[] = [[$ctx->t('adm.edit_days', ['days' => $r['days']]), 'a:pd:' . $r['id']]];
            }
        }
        $kb[] = self::back($ctx);
        $edit ? $ctx->edit(implode("\n", $lines), Kb::inline($kb)) : $ctx->send(implode("\n", $lines), Kb::inline($kb));
    }

    public static function statsData(): array
    {
        $db = App::db();
        return [
            'users' => (int)$db->val('SELECT COUNT(*) FROM tb_users'),
            'profiles' => (int)$db->val("SELECT COUNT(*) FROM tb_users WHERE reg_step = 'done' AND status = 'active'"),
            'premium' => (int)$db->val('SELECT COUNT(*) FROM tb_users WHERE premium_until > UTC_TIMESTAMP()'),
            'chats' => (int)$db->val("SELECT COUNT(*) FROM tb_chats WHERE status = 'active'"),
            'xtr' => (int)$db->val("SELECT COALESCE(SUM(amount), 0) FROM tb_orders WHERE status = 'paid' AND currency = 'XTR'"),
            'reports' => (int)$db->val("SELECT COUNT(*) FROM tb_reports WHERE status = 'open'"),
            'unsent' => (int)$db->val("SELECT COUNT(*) FROM tb_outbox WHERE status IN ('pending','sending')"),
            'verified' => (int)$db->val('SELECT COUNT(*) FROM tb_user_ext WHERE verified = 1'),
            'hidden' => (int)$db->val('SELECT COUNT(*) FROM tb_user_ext WHERE mod_hidden = 1'),
            'vpending' => (int)$db->val("SELECT COUNT(*) FROM tb_verifications WHERE status = 'pending'"),
            'lmtoday' => (int)$db->val('SELECT COUNT(*) FROM tb_like_msgs WHERE created_at >= UTC_DATE()'),
            'new24' => (int)$db->val('SELECT COUNT(*) FROM tb_users WHERE created_at > UTC_TIMESTAMP() - INTERVAL 1 DAY'),
            'active24' => (int)$db->val('SELECT COUNT(*) FROM tb_users WHERE last_seen_at > UTC_TIMESTAMP() - INTERVAL 1 DAY'),
            'matches' => (int)$db->val('SELECT COUNT(*) FROM tb_matches'),
            'blocks' => (int)$db->val('SELECT COUNT(*) FROM tb_blocks'),
            'refs' => (int)$db->val('SELECT COUNT(*) FROM tb_referrals'),
            'refpaid' => (int)$db->val('SELECT COUNT(*) FROM tb_referrals WHERE rewarded_at IS NOT NULL'),
            'xtr7' => (int)$db->val("SELECT COALESCE(SUM(amount), 0) FROM tb_orders WHERE status = 'paid' AND currency = 'XTR' AND paid_at > UTC_TIMESTAMP() - INTERVAL 7 DAY"),
            'xtr30' => (int)$db->val("SELECT COALESCE(SUM(amount), 0) FROM tb_orders WHERE status = 'paid' AND currency = 'XTR' AND paid_at > UTC_TIMESTAMP() - INTERVAL 30 DAY"),
            'rt24' => (int)$db->val('SELECT COUNT(*) FROM tb_notices WHERE sent_at > UTC_TIMESTAMP() - INTERVAL 1 DAY'),
            'rvpending' => (int)$db->val("SELECT COUNT(*) FROM tb_profile_reviews WHERE status = 'pending'"),
            'funnel' => self::funnel(),
        ];
    }

    /** Ro‘yxatdan o‘tish voronkasi: oxirgi 30 kunda yaratilgan foydalanuvchilar qaysi bosqichda turibdi. */
    public static function funnel(): string
    {
        $rows = App::db()->all(
            "SELECT reg_step, COUNT(*) AS n FROM tb_users WHERE created_at > UTC_TIMESTAMP() - INTERVAL 30 DAY GROUP BY reg_step"
        );
        $by = [];
        foreach ($rows as $r) {
            $by[$r['reg_step']] = (int)$r['n'];
        }
        $out = [];
        foreach (Registration::STEPS as $s) {
            $out[] = $s . ': ' . ($by[$s] ?? 0);
        }
        return implode(' · ', $out);
    }

    private static function stats(Ctx $ctx): void
    {
        $d = self::statsData();
        $ctx->edit($ctx->t('adm.stats_text', $d) . "\n" . $ctx->t('adm.stats_more', $d) . "\n" . $ctx->t('adm.stats_growth', $d), Kb::inline([self::back($ctx)]));
    }

    private static function broadcasts(Ctx $ctx): void
    {
        $rows = App::db()->all('SELECT id, status, enqueued, created_at FROM tb_broadcasts ORDER BY id DESC LIMIT 5');
        $lines = [$ctx->t('adm.bc_title')];
        foreach ($rows as $r) {
            $lines[] = '#' . $r['id'] . ' · ' . $r['status'] . ' · ' . $r['enqueued'] . ' · ' . substr((string)$r['created_at'], 0, 16);
        }
        $ctx->edit(implode("\n", $lines), Kb::inline([[[$ctx->t('adm.bc_new'), 'a:bn']], self::back($ctx)]));
    }
}
