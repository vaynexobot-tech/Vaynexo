<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Qidiruv, anketa kartalari, reaksiyalar va matchlar.
 * Har bir karta tugmasi foydalanuvchida saqlangan bir martalik nonce ga bog‘langan:
 * callbackda nishon ID si yo‘q, shuning uchun uni soxtalashtirib bo‘lmaydi; eski nonce ishlamaydi.
 */
final class Search
{
    public const LIST_CTX = ['ll' => 'like', 'ls' => 'super', 'lb' => 'save'];

    public const AGE_PRESETS = ['1' => [18, 24], '2' => [25, 34], '3' => [35, 44], '4' => [45, 99]];
    private const HIDDEN = 'NOT EXISTS (SELECT 1 FROM tb_user_ext hx WHERE hx.user_id = u.id AND hx.mod_hidden = 1)';

    public static function filterText(Ctx $ctx): string
    {
        $u = $ctx->u;
        $age = $u['pref_age_min'] !== null && $u['pref_age_min'] !== ''
            ? (int)$u['pref_age_min'] . '–' . (int)$u['pref_age_max']
            : $ctx->t('filter.any');
        $goal = in_array($u['pref_goal'] ?? null, Users::GOALS, true) ? $ctx->t('goal.' . $u['pref_goal']) : $ctx->t('filter.any');
        return $ctx->t('filter.summary', ['age' => $age, 'goal' => $goal]);
    }

    public static function menu(Ctx $ctx, bool $edit = false): void
    {
        $rows = [
            [[$ctx->t('search.men'), 's:m']],
            [[$ctx->t('search.women'), 's:f']],
            [[$ctx->t('search.any'), 's:a']],
            [[$ctx->t('filter.age_btn'), 's:age'], [$ctx->t('filter.goal_btn'), 's:goal']],
        ];
        if (Settings::on('verify_enabled')) {
            $rows[] = [[$ctx->t((int)$ctx->u['pref_verified'] === 1 ? 'filter.verified_on' : 'filter.verified_off'), 's:ver']];
        }
        $rows[] = [[$ctx->t('btn.back'), 'm:home']];
        $text = $ctx->t('search.title') . "\n\n" . self::filterText($ctx);
        $edit ? $ctx->edit($text, Kb::inline($rows)) : $ctx->send($text, Kb::inline($rows));
    }

    public static function likesMenu(Ctx $ctx): void
    {
        $db = App::db();
        $c = [];
        foreach (self::LIST_CTX as $k => $kind) {
            $c[$k] = (int)$db->val(
                "SELECT COUNT(*) FROM tb_reactions r JOIN tb_users u ON u.id = r.from_id
                 WHERE r.to_id = ? AND r.kind = ? AND u.status = 'active' AND u.reg_step = 'done' AND " . self::HIDDEN
                . ' AND ' . Blocks::notBlockedSql('u.id'),
                [$ctx->uid, $kind, $ctx->uid, $ctx->uid]
            );
        }
        $ctx->send($ctx->t('likes.title'), Kb::inline([
            [[$ctx->t('likes.likes', ['n' => $c['ll']]), 'lk:l']],
            [[$ctx->t('likes.supers', ['n' => $c['ls']]), 'lk:s']],
            [[$ctx->t('likes.saves', ['n' => $c['lb']]), 'lk:b']],
            [[$ctx->t('btn.back'), 'm:home']],
        ]));
    }

    public static function callback(Ctx $ctx, array $p): void
    {
        $pfx = $p[0];
        if ($pfx === 'lm') {
            if (($ctx->u['state'] ?? '') === 'likemsg') {
                $ctx->setState(null);
            }
            $ctx->answer($ctx->t('likemsg.cancelled'));
            $ctx->edit($ctx->t('likemsg.cancelled'));
            return;
        }
        if ($pfx === 's' && in_array($p[1] ?? '', ['age', 'goal', 'ver', 'ag', 'gl'], true)) {
            self::filterCb($ctx, $p);
            return;
        }
        if ($pfx === 's') {
            $g = $p[1] ?? '';
            if (!in_array($g, ['m', 'f', 'a'], true)) {
                $ctx->answer($ctx->t('err.stale'));
                return;
            }
            $ctx->set(['search_pref' => $g, 'card_ctx' => 'srch', 'card_pos' => 0]);
            $ctx->answer();
            self::showNext($ctx);
            return;
        }
        if ($pfx === 'lk') {
            $map = ['l' => 'll', 's' => 'ls', 'b' => 'lb'];
            if (!isset($map[$p[1] ?? ''])) {
                $ctx->answer($ctx->t('err.stale'));
                return;
            }
            if ($p[1] === 'l' && Settings::on('likes_gate') && !Users::isPremium($ctx->u)) {
                $ctx->answer();
                $n = (int)App::db()->val(
                    "SELECT COUNT(*) FROM tb_reactions r JOIN tb_users u ON u.id = r.from_id
                     WHERE r.to_id = ? AND r.kind = 'like' AND u.status = 'active' AND u.reg_step = 'done' AND " . self::HIDDEN
                    . ' AND ' . Blocks::notBlockedSql('u.id'),
                    [$ctx->uid, $ctx->uid, $ctx->uid]
                );
                $ctx->send($ctx->t('likes.locked', ['n' => $n]), Kb::inline([[[$ctx->t('likes.get_premium'), 'pm:menu']], [[$ctx->t('btn.back'), 'm:home']]]));
                return;
            }
            $ctx->answer();
            self::startList($ctx, $map[$p[1]]);
            return;
        }
        // r:<kind>:<nonce>
        self::react($ctx, $p[1] ?? '', $p[2] ?? '');
    }

    private static function filterCb(Ctx $ctx, array $p): void
    {
        $a = $p[1];
        $v = $p[2] ?? '';
        $ctx->answer();
        if ($a === 'age') {
            $rows = [];
            foreach (self::AGE_PRESETS as $k => [$lo, $hi]) {
                $rows[] = [[$hi >= 99 ? $lo . '+' : $lo . '–' . $hi, 's:ag:' . $k]];
            }
            $rows[] = [[$ctx->t('filter.any'), 's:ag:0']];
            $ctx->edit($ctx->t('filter.age_prompt'), Kb::inline($rows));
            return;
        }
        if ($a === 'goal') {
            $ctx->edit($ctx->t('filter.goal_prompt'), Registration::goalKb($ctx, 's:gl:', 's:gl:any'));
            return;
        }
        if ($a === 'ag') {
            if ($v === '0') {
                $ctx->set(['pref_age_min' => null, 'pref_age_max' => null]);
            } elseif (isset(self::AGE_PRESETS[$v])) {
                $ctx->set(['pref_age_min' => self::AGE_PRESETS[$v][0], 'pref_age_max' => self::AGE_PRESETS[$v][1]]);
            } else {
                return;
            }
        } elseif ($a === 'gl') {
            if ($v === 'any') {
                $ctx->set(['pref_goal' => null]);
            } elseif (in_array($v, Users::GOALS, true)) {
                $ctx->set(['pref_goal' => $v]);
            } else {
                return;
            }
        } elseif ($a === 'ver') {
            $ctx->set(['pref_verified' => (int)$ctx->u['pref_verified'] === 1 ? 0 : 1]);
        }
        self::menu($ctx, true);
    }

    public static function startList(Ctx $ctx, string $c): void
    {
        $ctx->set(['card_ctx' => $c, 'card_pos' => 0]);
        self::showNext($ctx);
    }

    public static function showNext(Ctx $ctx): void
    {
        $c = (string)($ctx->u['card_ctx'] ?? '');
        $target = null;
        if ($c === 'srch') {
            $target = self::candidate($ctx->u);
        } elseif (isset(self::LIST_CTX[$c]) || $c === 'sv') {
            $target = self::listItem($ctx->uid, $c, (int)$ctx->u['card_pos']);
        }
        if ($target === null) {
            $ctx->set(['card_nonce' => null, 'card_target' => null]);
            $key = $c === 'srch' ? 'search.empty' : 'list.empty';
            $ctx->send($ctx->t($key), Kb::inline([[[$ctx->t('btn.back'), 'm:home']]]));
            return;
        }
        $u = Users::find($target);
        if (!Users::isVisible($u)) {
            $ctx->set(['card_nonce' => null, 'card_target' => null]);
            $ctx->send($ctx->t('list.empty'));
            return;
        }
        $nonce = bin2hex(random_bytes(6));
        $ctx->set(['card_nonce' => $nonce, 'card_target' => $target]);
        if ($c === 'srch') {
            App::db()->exec(
                'INSERT INTO tb_seen (viewer_id, target_id, seen_at) VALUES (?, ?, UTC_TIMESTAMP())
                 ON DUPLICATE KEY UPDATE seen_at = VALUES(seen_at)',
                [$ctx->uid, $target]
            );
        }
        $rows = [[[$ctx->t('card.like'), 'r:l:' . $nonce], [$ctx->t('card.super'), 'r:s:' . $nonce]]];
        if (Settings::likeMsgMode() !== 'off') {
            $rows[] = [[$ctx->t('card.likemsg'), 'r:m:' . $nonce]];
        }
        $rows[] = [[$ctx->t('card.save'), 'r:b:' . $nonce], [$ctx->t('card.report'), 'r:p:' . $nonce], [$ctx->t('card.next'), 'r:n:' . $nonce]];
        $rows[] = [[$ctx->t('card.block'), 'r:x:' . $nonce]];
        $extra = null;
        if (isset(self::LIST_CTX[$c]) && $c !== 'lb') {
            $m = App::db()->val(
                "SELECT text FROM tb_like_msgs WHERE from_id = ? AND to_id = ? AND status = 'delivered' ORDER BY id DESC LIMIT 1",
                [$target, $ctx->uid]
            );
            if ($m !== null) {
                $extra = $ctx->t('likemsg.in_card', ['text' => (string)$m]);
            }
        }
        Profile::sendCard($ctx, $u, Kb::inline($rows), false, null, $extra);
    }

    /**
     * Keyingi nomzod. Qat’iy shartlar WHERE da (jins filtri, 18+, suspended emas, o‘zi emas,
     * 24 soatda ko‘rilmagan). Boost va hudud faqat ORDER BY da: boost filtrni chetlab o‘tmaydi.
     */
    public static function candidate(array $me): ?int
    {
        $pref = $me['search_pref'] ?? 'a';
        $params = [(int)$me['id'], (int)$me['id'], (int)$me['id'], (int)$me['id'], (int)$me['id']];
        $gender = '';
        if ($pref === 'm' || $pref === 'f') {
            $gender = ' AND u.gender = ?';
            $params[] = $pref;
        }
        $ext = ' AND COALESCE(x.mod_hidden, 0) = 0';
        if (($me['pref_age_min'] ?? null) !== null && ($me['pref_age_max'] ?? null) !== null) {
            $ext .= ' AND x.age BETWEEN ? AND ?';
            $params[] = (int)$me['pref_age_min'];
            $params[] = (int)$me['pref_age_max'];
        }
        if (in_array($me['pref_goal'] ?? null, Users::GOALS, true)) {
            $ext .= ' AND x.goal = ?';
            $params[] = $me['pref_goal'];
        }
        if ((int)($me['pref_verified'] ?? 0) === 1 && Settings::on('verify_enabled')) {
            $ext .= ' AND x.verified = 1';
        }
        $shared = '0';
        foreach (Users::interests($me) as $i) {
            $shared .= " + (FIND_IN_SET('" . $i . "', u.interests) > 0)";   // $i faqat Users::INTERESTS dan (whitelist)
        }
        $myAge = Users::age($me);
        $ageOrder = $myAge !== null ? 'ABS(COALESCE(x.age, ' . $myAge . ') - ' . $myAge . ') ASC,' : '';
        $params[] = (string)($me['gender'] ?? '');
        $params[] = (int)($me['region'] ?? 0);
        $sql = "SELECT u.id FROM tb_users u LEFT JOIN tb_user_ext x ON x.user_id = u.id
                WHERE u.id <> ? AND u.reg_step = 'done' AND u.age_confirmed = 1 AND u.status = 'active'
                  AND NOT EXISTS (SELECT 1 FROM tb_seen s WHERE s.viewer_id = ? AND s.target_id = u.id AND s.seen_at > UTC_TIMESTAMP() - INTERVAL 24 HOUR)
                  AND NOT EXISTS (SELECT 1 FROM tb_reactions r WHERE r.from_id = ? AND r.to_id = u.id AND r.kind IN ('like','super'))
                  AND " . Blocks::notBlockedSql('u.id') . "
                  $gender $ext
                ORDER BY
                  EXISTS (SELECT 1 FROM tb_boosts b WHERE b.user_id = u.id AND b.audience = ? AND b.starts_at <= UTC_TIMESTAMP() AND b.expires_at > UTC_TIMESTAMP()) DESC,
                  (u.region = ?) DESC,
                  ($shared) DESC,
                  $ageOrder
                  u.last_seen_at DESC, u.id ASC
                LIMIT 1";
        $id = App::db()->val($sql, $params);
        return $id === null ? null : (int)$id;
    }

    public static function listItem(int $me, string $c, int $pos): ?int
    {
        $pos = max(0, $pos);
        $nb = ' AND ' . Blocks::notBlockedSql('u.id');
        if ($c === 'sv') {
            $sql = "SELECT r.to_id FROM tb_reactions r JOIN tb_users u ON u.id = r.to_id
                    WHERE r.from_id = ? AND r.kind = 'save' AND u.status = 'active' AND u.reg_step = 'done' AND " . self::HIDDEN . $nb . "
                    ORDER BY r.created_at DESC, r.id DESC LIMIT 1 OFFSET $pos";
            $id = App::db()->val($sql, [$me, $me, $me]);
        } else {
            $sql = "SELECT r.from_id FROM tb_reactions r JOIN tb_users u ON u.id = r.from_id
                    WHERE r.to_id = ? AND r.kind = ? AND u.status = 'active' AND u.reg_step = 'done' AND " . self::HIDDEN . $nb . "
                    ORDER BY r.created_at DESC, r.id DESC LIMIT 1 OFFSET $pos";
            $id = App::db()->val($sql, [$me, self::LIST_CTX[$c], $me, $me]);
        }
        return $id === null ? null : (int)$id;
    }

    private static function react(Ctx $ctx, string $k, string $nonce): void
    {
        $cur = $ctx->u['card_nonce'] ?? null;
        if (!in_array($k, ['l', 's', 'b', 'n', 'm', 'p', 'x'], true) || !is_string($cur) || !preg_match('/^[0-9a-f]{12}$/', $nonce) || !hash_equals($cur, $nonce) || empty($ctx->u['card_target'])) {
            $ctx->answer($ctx->t('err.stale'));
            return;
        }
        $targetId = (int)$ctx->u['card_target'];
        $isList = ($ctx->u['card_ctx'] ?? '') !== 'srch';
        $advance = function () use ($ctx, $isList): void {
            if ($isList) {
                $ctx->set(['card_pos' => (int)$ctx->u['card_pos'] + 1]);
            }
            self::showNext($ctx);
        };
        if ($k === 'n') {
            $ctx->answer();
            $advance();
            return;
        }
        $target = Users::find($targetId);
        if (!Users::isVisible($target) || $targetId === $ctx->uid) {
            $ctx->answer($ctx->t('err.unavailable'));
            $advance();
            return;
        }
        $db = App::db();
        if ($k === 'x') {
            Blocks::add($ctx, $targetId);
            $ctx->answer($ctx->t('card.blocked'));
            $advance();
            return;
        }
        if ($k === 'p') {
            $ctx->setState('report', ['chat' => 0, 'reported' => $targetId]);
            $ctx->answer();
            $ctx->send($ctx->t('report.ask_card'), Kb::inline([[[$ctx->t('btn.cancel'), 'c:rx']]]));
            return;
        }
        if ($k === 'b') {
            $n = $db->exec("INSERT IGNORE INTO tb_reactions (from_id, to_id, kind, created_at) VALUES (?, ?, 'save', UTC_TIMESTAMP())", [$ctx->uid, $targetId]);
            $ctx->answer($ctx->t($n ? 'card.saved' : 'card.already_saved'));
            return;
        }
        $exists = $db->val("SELECT kind FROM tb_reactions WHERE from_id = ? AND to_id = ? AND kind IN ('like','super')", [$ctx->uid, $targetId]);
        if ($exists !== null) {
            $ctx->answer($ctx->t('card.already'));
            return;
        }
        if ($k === 'm') {
            if (Settings::likeMsgMode() === 'off') {
                $ctx->answer($ctx->t('err.stale'));
                return;
            }
            $ctx->setState('likemsg', ['t' => $targetId, 'n' => $nonce]);
            $ctx->answer();
            $ctx->send($ctx->t('likemsg.prompt', ['max' => self::LIKEMSG_MAX]), Kb::inline([[[$ctx->t('btn.cancel'), 'lm:x']]]));
            return;
        }
        $kind = $k === 'l' ? 'like' : 'super';
        if (!self::doLike($ctx, $target, $kind)) {
            return;
        }
        $advance();
    }

    public const LIKEMSG_MAX = 300;

    /** Like/super ni yozadi, mutual bo‘lsa match. false = limit tugagan. */
    private static function doLike(Ctx $ctx, array $target, string $kind, ?string $note = null): bool
    {
        $db = App::db();
        $targetId = (int)$target['id'];
        if (Blocks::between($ctx->uid, $targetId)) {
            $ctx->answer($ctx->t('err.unavailable'), true);
            return false;
        }
        if (!Limits::consume($ctx, $kind)) {
            return false;
        }
        $db->exec('INSERT INTO tb_reactions (from_id, to_id, kind, created_at) VALUES (?, ?, ?, UTC_TIMESTAMP())', [$ctx->uid, $targetId, $kind]);
        App::hook('after_reaction');
        $mutual = $db->val(
            "SELECT 1 FROM tb_reactions WHERE from_id = ? AND to_id = ? AND kind IN ('like','super') LIMIT 1 LOCK IN SHARE MODE",
            [$targetId, $ctx->uid]
        );
        $ctx->answer($ctx->t($kind === 'like' ? 'card.liked' : 'card.supered'));
        $tl = Lang::norm($target['lang'] ?? null);
        if ($note !== null) {
            $ctx->api('sendMessage', [
                'chat_id' => $targetId,
                'text' => Lang::t($tl, 'likemsg.notify', ['text' => $note]),
                'reply_markup' => Kb::inline([[[Lang::t($tl, 'likemsg.view'), 'lk:l']]]),
                'protect_content' => true,
            ], $targetId);
        }
        if ($mutual) {
            self::createMatch($ctx, $target);
        } elseif ($kind === 'super' && $note === null) {
            $ctx->api('sendMessage', ['chat_id' => $targetId, 'text' => Lang::t($tl, 'notify.super')], $targetId);
        }
        return true;
    }

    /**
     * Like bilan xabar: uzunlik, havola/@username va taqiqlangan so‘zlar tekshiriladi.
     * Admin «moderatsiya» rejimini yoqqan bo‘lsa xabar admin tasdig‘idan keyin yetkaziladi.
     * @return array{0:string,1:?string} [holat, sabab] holat: ok | len | link | stop
     */
    public static function checkLikeMsg(string $text): array
    {
        $t = trim((string)preg_replace('/[ \t]+/u', ' ', $text));
        $len = mb_strlen($t);
        if ($len < 1 || $len > self::LIKEMSG_MAX || preg_match('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', $t)) {
            return ['len', null];
        }
        if (Settings::on('likemsg_links') && preg_match('~(https?://|www\.|t\.me/|telegram\.(me|dog)|tg://|@[a-z0-9_]{4,}|\b[a-z0-9-]{2,}\.(com|ru|uz|net|org|me|io|xyz|link)\b)~iu', $t)) {
            return ['link', null];
        }
        $low = mb_strtolower($t);
        foreach (Settings::stopwords() as $w) {
            if (str_contains($low, $w)) {
                return ['stop', $w];
            }
        }
        return ['ok', $t];
    }

    public static function likeMsgInput(Ctx $ctx, array $msg): void
    {
        $d = $ctx->stateData();
        $text = isset($msg['text']) && is_string($msg['text']) ? $msg['text'] : null;
        $cancel = Kb::inline([[[$ctx->t('btn.cancel'), 'lm:x']]]);
        if ($text === null) {
            $ctx->send($ctx->t('likemsg.need_text'), $cancel);
            return;
        }
        $targetId = (int)($d['t'] ?? 0);
        $nonce = (string)($d['n'] ?? '');
        $cur = (string)($ctx->u['card_nonce'] ?? '');
        if ($targetId <= 0 || $cur === '' || !hash_equals($cur, $nonce) || (int)$ctx->u['card_target'] !== $targetId || Settings::likeMsgMode() === 'off') {
            $ctx->setState(null);
            $ctx->send($ctx->t('err.stale'));
            return;
        }
        [$res, $val] = self::checkLikeMsg($text);
        $db = App::db();
        if ($res === 'len') {
            $ctx->send($ctx->t('likemsg.len', ['max' => self::LIKEMSG_MAX]), $cancel);
            return;
        }
        if ($res === 'link') {
            $ctx->send($ctx->t('likemsg.no_links'), $cancel);
            return;
        }
        if ($res === 'stop') {
            $db->exec(
                "INSERT INTO tb_like_msgs (from_id, to_id, text, status, reason, created_at) VALUES (?, ?, ?, 'blocked', 'stopword', UTC_TIMESTAMP())",
                [$ctx->uid, $targetId, mb_substr(trim($text), 0, self::LIKEMSG_MAX)]
            );
            $ctx->send($ctx->t('likemsg.blocked'), $cancel);
            return;
        }
        $target = Users::find($targetId);
        if (!Users::isVisible($target)) {
            $ctx->setState(null);
            $ctx->send($ctx->t('err.unavailable'));
            return;
        }
        if ($db->val("SELECT 1 FROM tb_reactions WHERE from_id = ? AND to_id = ? AND kind IN ('like','super')", [$ctx->uid, $targetId]) !== null) {
            $ctx->setState(null);
            $ctx->send($ctx->t('card.already'));
            return;
        }
        $moderate = Settings::likeMsgMode() === 'moderate';
        $ctx->setState(null);
        if (!self::doLike($ctx, $target, 'like', $moderate ? null : $val)) {
            return;
        }
        $db->exec(
            'INSERT INTO tb_like_msgs (from_id, to_id, text, status, created_at) VALUES (?, ?, ?, ?, UTC_TIMESTAMP())',
            [$ctx->uid, $targetId, $val, $moderate ? 'pending' : 'delivered']
        );
        if ($moderate) {
            Admin::notify($ctx, 'admin.likemsg_new');
        }
        $ctx->send($ctx->t($moderate ? 'likemsg.sent_moderation' : 'likemsg.sent'));
        self::showNext($ctx);
    }

    public static function createMatch(Ctx $ctx, array $other): void
    {
        $a = min($ctx->uid, (int)$other['id']);
        $b = max($ctx->uid, (int)$other['id']);
        $db = App::db();
        $n = $db->exec('INSERT IGNORE INTO tb_matches (user_a, user_b, created_at) VALUES (?, ?, UTC_TIMESTAMP())', [$a, $b]);
        if ($n === 0) {
            return;
        }
        $mid = $db->lastId();
        $ctx->send($ctx->t('match.new', ['name' => $other['name']]), Kb::inline([[[$ctx->t('match.start'), 'c:s:' . $mid]]]));
        $ol = Lang::norm($other['lang'] ?? null);
        $ctx->api('sendMessage', [
            'chat_id' => (int)$other['id'],
            'text' => Lang::t($ol, 'match.new', ['name' => (string)$ctx->u['name']]),
            'reply_markup' => Kb::inline([[[Lang::t($ol, 'match.start'), 'c:s:' . $mid]]]),
        ], (int)$other['id']);
    }
}
