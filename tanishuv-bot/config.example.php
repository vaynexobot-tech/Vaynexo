<?php
/*
 * NAMUNA. Bu faylni config.php nomi bilan nusxalang va qiymatlarni to‘ldiring.
 * Bu faylda hech qanday maxfiy qiymat yo‘q va bo‘lmasligi kerak.
 *
 * webhook_secret, setup_key, cron_key: har biri 64 belgili, bir-biridan FARQLI tasodifiy qiymat.
 * Faqat A-Z, a-z, 0-9 belgilaridan foydalaning (masalan 64 ta hex belgi).
 */
defined('TB_ROOT') || exit;

return [
    // Telegram @BotFather bergan token
    'bot_token' => '',
    'bot_username' => '',

    // MySQL / MariaDB
    'db' => [
        'host' => '',
        'port' => 3306,
        'name' => '',
        'user' => '',
        'pass' => '',
    ],

    // public/ papkasining HTTPS manzili (oxirida / siz)
    'public_url' => '',

    // Admin Telegram ID lari (raqam). Ruxsat har amalda shu ro‘yxatdan qayta tekshiriladi.
    'admin_ids' => [],

    'webhook_secret' => '',
    'setup_key' => '',
    'cron_key' => '',

    // /support va /paysupport da ko‘rsatiladigan aloqa (masalan @username)
    'support_contact' => '',

    'limits' => [
        'free_likes' => 30,
        'free_supers' => 1,
        'premium_likes' => 300,
        'premium_supers' => 10,
    ],

    // SMS/bank integratsiyasi. Hozir o‘chiq.
    'bank' => [
        'enabled' => false,
        'hmac_secret' => '',
        'max_skew' => 300,
    ],

    // CRON bitta chaqiruvda ishlaydigan maksimal vaqt (soniya)
    'cron_time_budget' => 20,
];
