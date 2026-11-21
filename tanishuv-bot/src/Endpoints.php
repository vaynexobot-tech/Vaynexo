<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

final class Endpoints
{
    public const TG_MAX_BODY = 1048576; // 1 MiB

    private static function out(int $code, array $body): never
    {
        if (!headers_sent()) {
            http_response_code($code);
            header('Content-Type: application/json; charset=utf-8');
            header('Cache-Control: no-store');
            header('X-Content-Type-Options: nosniff');
        }
        echo json_encode($body, JSON_UNESCAPED_UNICODE);
        exit;
    }

    private static function method(): string
    {
        return strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET'));
    }

    /** Body ni limit bilan o‘qiydi; limitdan oshsa null. */
    public static function readBody(int $limit): ?string
    {
        $len = $_SERVER['CONTENT_LENGTH'] ?? $_SERVER['HTTP_CONTENT_LENGTH'] ?? null;
        if ($len !== null && (int)$len > $limit) {
            return null;
        }
        $in = fopen('php://input', 'rb');
        if ($in === false) {
            return '';
        }
        $data = stream_get_contents($in, $limit + 1);
        fclose($in);
        if ($data === false) {
            return '';
        }
        return strlen($data) > $limit ? null : $data;
    }

    private static function boot(): void
    {
        try {
            App::loadConfig();
        } catch (\Throwable $e) {
            self::out(503, ['ok' => false, 'error' => 'config']);
        }
        if (App::configProblems()) {
            self::out(503, ['ok' => false, 'error' => 'config_insecure']);
        }
    }

    private static function finishRequest(): void
    {
        if (function_exists('fastcgi_finish_request')) {
            fastcgi_finish_request();
        } elseif (function_exists('litespeed_finish_request')) {
            litespeed_finish_request();
        } else {
            @ob_end_flush();
            @flush();
        }
    }

    public static function webhook(): void
    {
        if (self::method() !== 'POST') {
            header('Allow: POST');
            self::out(405, ['ok' => false, 'error' => 'method']);
        }
        self::boot();
        $got = (string)($_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '');
        if ($got === '' || !hash_equals((string)App::cfg('webhook_secret'), $got)) {
            self::out(403, ['ok' => false, 'error' => 'forbidden']);
        }
        $raw = self::readBody(self::TG_MAX_BODY);
        if ($raw === null) {
            self::out(413, ['ok' => false, 'error' => 'too_large']);
        }
        $upd = json_decode($raw, true, 64);
        if (!is_array($upd) || !isset($upd['update_id'])) {
            self::out(400, ['ok' => false, 'error' => 'invalid_json']);
        }
        try {
            $r = Bot::handleUpdate($upd);
        } catch (\Throwable $e) {
            Log::error('update ' . (int)($upd['update_id'] ?? 0), $e);
            self::out(500, ['ok' => false, 'error' => 'retry']);
        }
        ignore_user_abort(true);
        http_response_code(200);
        header('Content-Type: application/json; charset=utf-8');
        echo '{"ok":true}';
        self::finishRequest();
        if (!empty($r['out'])) {
            try {
                Outbox::process(microtime(true) + (float)App::cfg('webhook_send_budget', 4), 30, $r['out']);
            } catch (\Throwable $e) {
                Log::error('outbox after webhook', $e);
            }
        }
        exit;
    }

    public static function cron(): void
    {
        if (!in_array(self::method(), ['GET', 'POST'], true)) {
            header('Allow: GET, POST');
            self::out(405, ['ok' => false, 'error' => 'method']);
        }
        self::boot();
        $key = (string)($_SERVER['HTTP_X_CRON_KEY'] ?? ($_GET['key'] ?? ''));
        if ($key === '' || !hash_equals((string)App::cfg('cron_key'), $key)) {
            self::out(403, ['ok' => false, 'error' => 'forbidden']);
        }
        $budget = max(5, min(55, (int)App::cfg('cron_time_budget', 20)));
        $met = (int)ini_get('max_execution_time');
        if ($met > 0 && $met - 5 < $budget) {
            $budget = max(5, $met - 5);
        }
        @set_time_limit($budget + 15);
        ignore_user_abort(true);
        try {
            $st = Cron::run(microtime(true) + $budget);
        } catch (\Throwable $e) {
            Log::error('cron', $e);
            self::out(500, ['ok' => false, 'error' => 'cron_failed']);
        }
        self::out(200, ['ok' => true] + $st);
    }

    public static function bank(): void
    {
        if (self::method() !== 'POST') {
            header('Allow: POST');
            self::out(405, ['ok' => false, 'error' => 'method']);
        }
        self::boot();
        $raw = self::readBody(Bank::MAX_BODY);
        if ($raw === null) {
            self::out(413, ['ok' => false, 'error' => 'body_too_large']);
        }
        try {
            [$code, $body] = Bank::handle($raw, $_SERVER['HTTP_X_BANK_TIMESTAMP'] ?? null, $_SERVER['HTTP_X_BANK_SIGNATURE'] ?? null);
        } catch (\Throwable $e) {
            Log::error('bank', $e);
            self::out(500, ['ok' => false, 'error' => 'internal']);
        }
        self::out($code, $body);
    }
}
