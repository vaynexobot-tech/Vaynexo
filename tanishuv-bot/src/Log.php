<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/** Kichik log. Token, parol va kalitlar har doim yashiriladi. Hajm 512 KiB bilan cheklangan. */
final class Log
{
    public static function scrub(string $s): string
    {
        foreach (App::secrets() as $secret) {
            $s = str_replace($secret, '***', $s);
        }
        // Telegram bot token ko‘rinishidagi har qanday qatorni yashirish
        $s = (string)preg_replace('~\b\d{6,12}:[A-Za-z0-9_-]{30,}\b~', '***', $s);
        return $s;
    }

    public static function error(string $msg, ?\Throwable $e = null): void
    {
        if ($e) {
            $msg .= ' | ' . get_class($e) . ': ' . $e->getMessage() . ' @' . basename($e->getFile()) . ':' . $e->getLine();
        }
        self::write('ERROR', $msg);
    }

    public static function info(string $msg): void
    {
        self::write('INFO', $msg);
    }

    private static function write(string $level, string $msg): void
    {
        $line = gmdate('Y-m-d H:i:s') . " [$level] " . self::scrub(mb_substr($msg, 0, 2000)) . "\n";
        $dir = TB_ROOT . '/storage';
        $file = $dir . '/app.log';
        if (!is_dir($dir) || !is_writable($dir)) {
            error_log(rtrim($line));
            return;
        }
        if (is_file($file) && filesize($file) > 512 * 1024) {
            @rename($file, $file . '.1');
        }
        @file_put_contents($file, $line, FILE_APPEND | LOCK_EX);
    }
}
