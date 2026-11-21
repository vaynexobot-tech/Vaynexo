<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

final class Router
{
    public const COMMANDS = ['start', 'language', 'id', 'terms', 'privacy', 'support', 'paysupport', 'invite', 'blocks', 'delete'];

    public static function message(Ctx $ctx, array $msg): void
    {
        if (isset($msg['successful_payment']) && is_array($msg['successful_payment'])) {
            Payments::success($ctx, $msg['successful_payment']);
            return;
        }
        Registration::upgrade($ctx);
        $text = isset($msg['text']) && is_string($msg['text']) ? $msg['text'] : null;
        if ($text !== null && str_starts_with($text, '/')) {
            $cmd = strtolower(explode(' ', $text, 2)[0]);
            $cmd = substr(explode('@', $cmd, 2)[0], 1);
            $arg = trim((string)(explode(' ', $text, 2)[1] ?? ''));
            self::command($ctx, $cmd, $arg);
            return;
        }
        if (!empty($ctx->u['active_chat_id'])) {
            Chat::relay($ctx, $msg);
            return;
        }
        $state = (string)($ctx->u['state'] ?? '');
        if ($text !== null && Users::isComplete($ctx->u)) {
            $item = Menu::resolve($text);
            if ($item !== null) {
                if ($state !== '') {
                    $ctx->setState(null);
                }
                Menu::open($ctx, $item);
                return;
            }
        }
        if (str_starts_with($state, 'adm:')) {
            Admin::input($ctx, $msg);
            return;
        }
        if ($state === 'likemsg' && Users::isComplete($ctx->u)) {
            Search::likeMsgInput($ctx, $msg);
            return;
        }
        if ($state === 'verify' && Users::isComplete($ctx->u)) {
            Profile::verifyInput($ctx, $msg);
            return;
        }
        if ($state === 'report') {
            Chat::reportInput($ctx, $msg);
            return;
        }
        if (str_starts_with($state, 'edit:') && (Users::isComplete($ctx->u) || ($ctx->u['reg_step'] ?? '') === 'review')) {
            Profile::input($ctx, $msg);
            return;
        }
        if (!Users::isComplete($ctx->u)) {
            Registration::message($ctx, $msg);
            return;
        }
        Menu::home($ctx, 'menu.hint');
    }

    public static function command(Ctx $ctx, string $cmd, string $arg = ''): void
    {
        switch ($cmd) {
            case 'start':
                Referrals::capture($ctx, $arg);
                if (!empty($ctx->u['active_chat_id'])) {
                    Chat::remind($ctx);
                } elseif (!Users::isComplete($ctx->u)) {
                    Registration::resume($ctx);
                } else {
                    if (!empty($ctx->u['state'])) {
                        $ctx->setState(null);
                    }
                    Menu::home($ctx, 'menu.welcome_back');
                }
                return;
            case 'language':
                Registration::askLang($ctx, true);
                return;
            case 'id':
                $ctx->send($ctx->t('cmd.id', ['id' => $ctx->uid]));
                return;
            case 'terms':
                $ctx->send($ctx->t('cmd.terms'));
                return;
            case 'privacy':
                $ctx->send($ctx->t('cmd.privacy'));
                return;
            case 'support':
                $ctx->send($ctx->t('cmd.support', ['contact' => self::contact()]));
                return;
            case 'paysupport':
                $ctx->send($ctx->t('cmd.paysupport', ['contact' => self::contact()]));
                return;
            case 'invite':
                if (Users::isComplete($ctx->u)) {
                    Referrals::command($ctx);
                } else {
                    $ctx->send($ctx->t('err.finish_reg'));
                }
                return;
            case 'blocks':
                Blocks::command($ctx);
                return;
            case 'delete':
                $ctx->send($ctx->t('delete.confirm'), Kb::inline([
                    [[$ctx->t('delete.yes'), 'del:yes'], [$ctx->t('delete.no'), 'del:no']],
                ]));
                return;
            case 'admin':
                Admin::open($ctx);
                return;
            default:
                $ctx->send($ctx->t('cmd.unknown'));
        }
    }

    public static function contact(): string
    {
        $c = trim((string)App::cfg('support_contact', ''));
        return $c !== '' ? $c : '—';
    }

    public static function callback(Ctx $ctx, string $data): void
    {
        if ($data === '' || strlen($data) > 64) {
            $ctx->answer($ctx->t('err.stale'));
            return;
        }
        $parts = explode(':', $data);
        $pfx = $parts[0];
        if ($pfx !== 'lang' && $pfx !== 'reg') {
            Registration::upgrade($ctx);
        }
        $needsActive = ['s', 'r', 'lk', 'lm', 'pr', 'e', 'c', 'pm', 'bs', 'm', 'bk'];
        if (in_array($pfx, $needsActive, true)) {
            $reviewEdit = ($ctx->u['reg_step'] ?? '') === 'review' && (int)$ctx->u['age_confirmed'] === 1 && in_array($pfx, ['pr', 'e'], true);
            if (!Users::isComplete($ctx->u) && !$reviewEdit) {
                $ctx->answer($ctx->t('err.finish_reg'), true);
                Registration::resume($ctx);
                return;
            }
            if (($ctx->u['status'] ?? '') !== 'active' && $pfx !== 'c') {
                $ctx->answer($ctx->t('err.suspended'), true);
                return;
            }
        }
        switch ($pfx) {
            case 'lang':
                Registration::langCb($ctx, $parts[1] ?? '');
                return;
            case 'reg':
                Registration::callback($ctx, $parts);
                return;
            case 'm':
                $ctx->answer();
                Menu::home($ctx, 'menu.title');
                return;
            case 's':
            case 'r':
            case 'lk':
            case 'lm':
                Search::callback($ctx, $parts);
                return;
            case 'pr':
            case 'e':
                Profile::callback($ctx, $parts);
                return;
            case 'c':
                Chat::callback($ctx, $parts);
                return;
            case 'pm':
            case 'bs':
                Payments::callback($ctx, $parts);
                return;
            case 'bk':
                Blocks::callback($ctx, $parts);
                return;
            case 'del':
                Profile::deleteCb($ctx, $parts[1] ?? '');
                return;
            case 'a':
                Admin::callback($ctx, $parts);
                return;
            default:
                $ctx->answer($ctx->t('err.stale'));
        }
    }
}
