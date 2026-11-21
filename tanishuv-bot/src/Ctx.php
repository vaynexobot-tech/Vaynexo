<?php
declare(strict_types=1);

namespace TB;

defined('TB_ROOT') || exit;

/** Bitta update ni qayta ishlash konteksti. */
final class Ctx
{
    public array $u;
    public string $lang;
    public array $out = [];
    private int $seq = 0;
    private bool $answered = false;

    public int $uid;
    public int $updateId;
    public ?array $msg;
    public ?array $cb;

    public function __construct(int $uid, int $updateId, ?array $msg, ?array $cb)
    {
        $this->uid = $uid;
        $this->updateId = $updateId;
        $this->msg = $msg;
        $this->cb = $cb;
        $this->u = Users::lock($uid);
        $this->lang = Lang::norm($this->u['lang'] ?? null);
        if (($this->u['lang'] ?? null) === null) {
            $lc = substr((string)(($msg['from'] ?? $cb['from'] ?? [])['language_code'] ?? ''), 0, 2);
            $this->lang = in_array($lc, Lang::LANGS, true) ? $lc : 'uz';
        }
    }

    public function t(string $k, array $p = []): string
    {
        return Lang::t($this->lang, $k, $p);
    }

    public function set(array $f): void
    {
        Users::update($this->uid, $f);
        foreach ($f as $k => $v) {
            $this->u[$k] = $v;
        }
        if (array_key_exists('lang', $f)) {
            $this->lang = Lang::norm($f['lang']);
        }
    }

    public function stateData(): array
    {
        $d = json_decode((string)($this->u['state_data'] ?? ''), true);
        return is_array($d) ? $d : [];
    }

    public function setState(?string $state, array $data = []): void
    {
        $this->set(['state' => $state, 'state_data' => $state === null ? null : json_encode($data, JSON_UNESCAPED_UNICODE)]);
    }

    public function api(string $method, array $params, ?int $chat = null, int $prio = 5): void
    {
        $chat ??= $this->uid;
        if ($chat === $this->uid && in_array($method, RegCleanup::TRACKED, true) && !RegCleanup::finished($this->u)) {
            $params[RegCleanup::KEY] = 1;
        }
        $id = Outbox::add($chat, $method, $params, 'u:' . $this->updateId . ':' . (++$this->seq), $prio);
        if ($id) {
            $this->out[] = $id;
        }
    }

    public function send(string $text, ?array $markup = null, ?int $chat = null): void
    {
        $chat ??= $this->uid;
        $p = ['chat_id' => $chat, 'text' => mb_substr($text, 0, 4000)];
        if ($markup !== null) {
            $p['reply_markup'] = $markup;
        }
        $this->api('sendMessage', $p, $chat);
    }

    /** Callback kelgan matnli xabarni tahrirlaydi, aks holda yangi xabar yuboradi. */
    public function edit(string $text, ?array $inline = null): void
    {
        $m = $this->cb['message'] ?? null;
        if ($m && isset($m['text']) && isset($m['message_id'])) {
            $p = ['chat_id' => $this->uid, 'message_id' => (int)$m['message_id'], 'text' => mb_substr($text, 0, 4000)];
            if ($inline !== null) {
                $p['reply_markup'] = $inline;
            }
            $this->api('editMessageText', $p);
            return;
        }
        $this->send($text, $inline);
    }

    public function answer(string $text = '', bool $alert = false): void
    {
        if (!$this->cb || $this->answered) {
            return;
        }
        $this->answered = true;
        $p = ['callback_query_id' => (string)$this->cb['id']];
        if ($text !== '') {
            $p['text'] = mb_substr($text, 0, 190);
            $p['show_alert'] = $alert;
        }
        $this->api('answerCallbackQuery', $p, null, 1);
    }

    public function finish(): void
    {
        $this->answer();
    }
}
