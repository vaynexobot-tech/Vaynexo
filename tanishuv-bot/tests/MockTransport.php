<?php
declare(strict_types=1);

namespace TB\Tests;

use TB\Transport;

/** Telegram API ning soxta (mock) transporti. Hech qanday tarmoq chaqiruvi yo‘q. */
final class MockTransport implements Transport
{
    /** @var array<int, array{method:string, params:array}> */
    public array $calls = [];
    /** user_id => file_id (Telegram profil rasmi) */
    public array $profilePhotos = [];
    /** method => callable(array $params): array  — maxsus javob */
    public array $responders = [];
    private int $msgId = 1000;

    public function call(string $method, array $params, int $timeout = 10): array
    {
        $this->calls[] = ['method' => $method, 'params' => $params];
        if (isset($this->responders[$method])) {
            return ($this->responders[$method])($params);
        }
        if ($method === 'getUserProfilePhotos') {
            $uid = (int)($params['user_id'] ?? 0);
            if (isset($this->profilePhotos[$uid])) {
                $f = $this->profilePhotos[$uid];
                return ['ok' => true, 'result' => ['total_count' => 1, 'photos' => [[
                    ['file_id' => $f . '_small', 'width' => 160, 'height' => 160],
                    ['file_id' => $f, 'width' => 640, 'height' => 640],
                ]]]];
            }
            return ['ok' => true, 'result' => ['total_count' => 0, 'photos' => []]];
        }
        if ($method === 'getMe') {
            return ['ok' => true, 'result' => ['id' => 1, 'is_bot' => true, 'username' => 'test_bot']];
        }
        $this->calls[array_key_last($this->calls)]['mid'] = ++$this->msgId;
        return ['ok' => true, 'result' => ['message_id' => $this->msgId]];
    }

    public function reset(): void
    {
        $this->calls = [];
    }

    public function to(int $chat): array
    {
        return array_values(array_filter($this->calls, static fn($c) => (int)($c['params']['chat_id'] ?? 0) === $chat));
    }

    public function last(int $chat, ?string $method = null): ?array
    {
        $c = $this->to($chat);
        if ($method !== null) {
            $c = array_values(array_filter($c, static fn($x) => $x['method'] === $method));
        }
        return $c ? end($c) : null;
    }

    public function byMethod(string $method): array
    {
        return array_values(array_filter($this->calls, static fn($c) => $c['method'] === $method));
    }
}
