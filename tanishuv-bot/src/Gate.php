<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Suhbat qulfi: match bo‘lgach suhbat boshlash uchun Premium YOKI majburiy kanallarga obuna kerak.
 * Faqat suhbatni BOSHLAGAN tomon tekshiriladi; sherigi bepul qo‘shiladi.
 * Obuna har safar Telegram getChatMember orqali jonli tekshiriladi (bot kanalda admin bo‘lishi shart).
 * API xatosi (masalan bot admin emas) bo‘lsa, foydalanuvchi to‘sib qo‘yilmaydi va xato logga yoziladi.
 */
final class Gate
{
    public const MAX_CHANNELS = 5;

    public static function enabled(): bool
    {
        return Settings::on('chat_gate');
    }

    /** @return array<int, array{ref:string,title:string,url:string}> */
    public static function channels(): array
    {
        $j = json_decode(Settings::get('gate_channels'), true);
        $out = [];
        foreach (is_array($j) ? $j : [] as $c) {
            if (is_array($c) && is_string($c['ref'] ?? null) && is_string($c['url'] ?? null)) {
                $out[] = ['ref' => $c['ref'], 'title' => (string)($c['title'] ?? $c['ref']), 'url' => $c['url']];
            }
        }
        return array_slice($out, 0, self::MAX_CHANNELS);
    }

    public static function saveChannels(array $list): void
    {
        Settings::set('gate_channels', (string)json_encode(array_values($list), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    }

    /** Qulf shu foydalanuvchiga tegishlimi? */
    public static function applies(Ctx $ctx): bool
    {
        return self::enabled() && !Users::isPremium($ctx->u) && !App::isAdmin($ctx->uid);
    }

    /** Obuna bo‘lmagan kanallar. */
    public static function missing(int $uid): array
    {
        $miss = [];
        foreach (self::channels() as $c) {
            $r = App::tg()->call('getChatMember', ['chat_id' => $c['ref'], 'user_id' => $uid], 8);
            if (empty($r['ok'])) {
                Log::error('gate getChatMember ' . $c['ref'] . ': ' . (string)($r['description'] ?? '?'));
                continue;
            }
            $st = (string)($r['result']['status'] ?? '');
            $in = in_array($st, ['member', 'administrator', 'creator'], true) || ($st === 'restricted' && !empty($r['result']['is_member']));
            if (!$in) {
                $miss[] = $c;
            }
        }
        return $miss;
    }

    /**
     * Suhbat boshlashdan oldin chaqiriladi. true = o‘tkazish mumkin.
     * Aks holda qulf xabari (kanal tugmalari, «Tekshirish», «Premium») yuboriladi.
     */
    public static function pass(Ctx $ctx, int $matchId): bool
    {
        if (!self::applies($ctx)) {
            return true;
        }
        $channels = self::channels();
        $miss = self::missing($ctx->uid);
        if ($channels && !$miss) {
            return true;
        }
        $rows = [];
        foreach ($miss as $c) {
            $rows[] = [[$ctx->t('gate.join', ['title' => $c['title']]), $c['url'], 'url']];
        }
        if ($channels) {
            $rows[] = [[$ctx->t('gate.check'), 'c:s:' . $matchId]];
        }
        $rows[] = [[$ctx->t('gate.premium'), 'pm:menu']];
        $ctx->answer();
        $ctx->send($ctx->t($channels ? 'gate.text' : 'gate.text_premium'), Kb::inline($rows));
        return false;
    }

    // ---------------- Admin ----------------

    public static function adminView(Ctx $ctx): void
    {
        $lines = [$ctx->t('adm.gate_title', ['on' => self::enabled() ? '✅' : '❌'])];
        $kb = [[[$ctx->t('adm.gate_toggle'), 'a:gct']]];
        foreach (self::channels() as $i => $c) {
            $lines[] = ($i + 1) . '. ' . $c['title'] . ' — ' . $c['ref'];
            $kb[] = [[$ctx->t('adm.gate_del', ['title' => $c['title']]), 'a:gcd:' . $i]];
        }
        if (count(self::channels()) < self::MAX_CHANNELS) {
            $kb[] = [[$ctx->t('adm.gate_add'), 'a:gca']];
        }
        $kb[] = [[$ctx->t('btn.back'), 'a:cfg']];
        $ctx->edit(implode("\n", $lines), Kb::inline($kb));
    }

    public static function adminCallback(Ctx $ctx, string $a, string $arg): void
    {
        switch ($a) {
            case 'gc':
                self::adminView($ctx);
                return;
            case 'gct':
                Settings::set('chat_gate', self::enabled() ? '0' : '1');
                Admin::audit($ctx, 'settings.chat_gate', null, Settings::get('chat_gate'));
                self::adminView($ctx);
                return;
            case 'gcd':
                $l = self::channels();
                if (isset($l[(int)$arg]) && ctype_digit($arg)) {
                    Admin::audit($ctx, 'gate.del', $l[(int)$arg]['ref']);
                    array_splice($l, (int)$arg, 1);
                    self::saveChannels($l);
                }
                self::adminView($ctx);
                return;
            case 'gca':
                $ctx->setState('adm:gch');
                $ctx->send($ctx->t('adm.gate_prompt'), Kb::inline([[[$ctx->t('btn.back'), 'a:gc']]]));
                return;
        }
    }

    /** "@kanal" yoki "-100123456 https://t.me/+invite" */
    public static function adminInput(Ctx $ctx, string $text): void
    {
        $parts = preg_split('/\s+/', trim($text)) ?: [];
        $ref = (string)($parts[0] ?? '');
        $url = (string)($parts[1] ?? '');
        $back = Kb::inline([[[$ctx->t('btn.back'), 'a:gc']]]);
        if (!preg_match('/^(@[A-Za-z0-9_]{4,32}|-100\d{5,15})$/', $ref)) {
            $ctx->send($ctx->t('adm.gate_bad_ref'), $back);
            return;
        }
        if ($url === '' && $ref[0] === '@') {
            $url = 'https://t.me/' . substr($ref, 1);
        }
        if (!preg_match('~^https://t\.me/[A-Za-z0-9_+/-]{3,100}$~', $url)) {
            $ctx->send($ctx->t('adm.gate_bad_url'), $back);
            return;
        }
        $chat = App::tg()->call('getChat', ['chat_id' => $ref], 8);
        if (empty($chat['ok'])) {
            $ctx->send($ctx->t('adm.gate_err', ['reason' => mb_substr(Log::scrub((string)($chat['description'] ?? '?')), 0, 120)]), $back);
            return;
        }
        $me = App::tg()->call('getMe', [], 8);
        $botId = (int)($me['result']['id'] ?? 0);
        $mem = App::tg()->call('getChatMember', ['chat_id' => $ref, 'user_id' => $botId], 8);
        if (empty($mem['ok']) || !in_array((string)($mem['result']['status'] ?? ''), ['administrator', 'creator'], true)) {
            $ctx->send($ctx->t('adm.gate_not_admin'), $back);
            return;
        }
        $list = self::channels();
        foreach ($list as $c) {
            if ($c['ref'] === $ref) {
                $ctx->setState(null);
                self::adminView($ctx);
                return;
            }
        }
        if (count($list) >= self::MAX_CHANNELS) {
            $ctx->send($ctx->t('adm.gate_full'), $back);
            return;
        }
        $list[] = ['ref' => $ref, 'title' => mb_substr((string)($chat['result']['title'] ?? $ref), 0, 40), 'url' => $url];
        self::saveChannels($list);
        Admin::audit($ctx, 'gate.add', $ref);
        $ctx->setState(null);
        self::adminView($ctx);
    }
}
