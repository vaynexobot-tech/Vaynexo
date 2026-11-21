<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

final class CurlTransport implements Transport
{
    private string $token;
    private string $base;

    public function __construct(string $token, string $base)
    {
        $this->token = $token;
        $this->base = $base;
    }

    public function call(string $method, array $params, int $timeout = 10): array
    {
        if ($this->token === '') {
            return ['ok' => false, 'error_code' => 0, 'description' => 'bot_token configda yo‘q'];
        }
        if (!preg_match('/^[A-Za-z]{2,40}$/', $method)) {
            return ['ok' => false, 'error_code' => 400, 'description' => 'bad method'];
        }
        $url = rtrim($this->base, '/') . '/bot' . $this->token . '/' . $method;
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => json_encode($params, JSON_UNESCAPED_UNICODE),
            CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_TIMEOUT => $timeout,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
        ]);
        $body = curl_exec($ch);
        $http = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $err = curl_error($ch);
        curl_close($ch);
        if ($body === false || $body === '') {
            return ['ok' => false, 'error_code' => 0, 'description' => Log::scrub('network: ' . $err)];
        }
        $j = json_decode((string)$body, true);
        if (!is_array($j)) {
            return ['ok' => false, 'error_code' => $http >= 500 ? $http : 0, 'description' => 'invalid JSON from Telegram (HTTP ' . $http . ')'];
        }
        if (!isset($j['ok'])) {
            $j['ok'] = false;
        }
        if (!$j['ok'] && !isset($j['error_code'])) {
            $j['error_code'] = $http;
        }
        if (isset($j['description'])) {
            $j['description'] = Log::scrub((string)$j['description']);
        }
        return $j;
    }
}
