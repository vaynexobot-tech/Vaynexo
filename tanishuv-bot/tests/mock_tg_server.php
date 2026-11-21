<?php
// Mock Telegram Bot API serveri (faqat testlar uchun, php -S bilan ishga tushiriladi).
if (PHP_SAPI !== 'cli-server') {
    exit;
}
$path = (string)parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$method = basename($path);
$body = (string)file_get_contents('php://input');
$log = getenv('MOCK_LOG');
if ($log) {
    file_put_contents($log, json_encode(['method' => $method, 'path_has_bot' => str_contains($path, '/bot'), 'body' => json_decode($body, true)]) . "\n", FILE_APPEND | LOCK_EX);
}
header('Content-Type: application/json');
switch ($method) {
    case 'getMe':
        echo json_encode(['ok' => true, 'result' => ['id' => 42, 'is_bot' => true, 'username' => 'mock_tanishuv_bot']]);
        break;
    case 'getWebhookInfo':
        echo json_encode(['ok' => true, 'result' => ['url' => '', 'pending_update_count' => 0]]);
        break;
    case 'getUserProfilePhotos':
        echo json_encode(['ok' => true, 'result' => ['total_count' => 0, 'photos' => []]]);
        break;
    default:
        echo json_encode(['ok' => true, 'result' => ['message_id' => 1]]);
}
