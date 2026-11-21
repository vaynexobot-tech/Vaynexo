<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/**
 * Telegram Bot API transporti. call() har doim massiv qaytaradi:
 * ['ok'=>bool, 'result'=>mixed, 'error_code'=>int, 'description'=>string, 'parameters'=>array]
 * error_code=0 tarmoq xatosini bildiradi.
 */
interface Transport
{
    public function call(string $method, array $params, int $timeout = 10): array;
}
