-- ============================================================================
-- Tanishuv bot — database.sql (YANGI BO‘SH BAZA uchun)
-- MySQL 5.7+/8.x yoki MariaDB 10.3+, InnoDB, utf8mb4.
--
-- phpMyAdmin: chap tomonda bazani (6af5109a8775e_vaynexo) tanlang → "Import" → shu fayl.
-- Bu faylda DROP DATABASE / DROP TABLE YO‘Q. Barcha jadvallar "tb_" prefiksli va
-- CREATE TABLE IF NOT EXISTS bilan yaratiladi; boshlang‘ich qatorlar INSERT IGNORE.
--
-- OGOHLANTIRISH: bazada tb_ jadvallari allaqachon bo‘lsa, bu faylni QAYTA IMPORT QILMANG.
-- (Mavjud jadvallarga tegmaydi, lekin yangilash uchun mo‘ljallanmagan.)
-- Eski loyihalar (kino-bot, VAYNEXO) jadvallari bilan bitta bazada bo‘lsa migration.sql dan foydalaning.
-- ============================================================================

SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE TABLE IF NOT EXISTS `tb_users` (
  `id` BIGINT NOT NULL COMMENT 'Telegram user ID',
  `lang` VARCHAR(2) NULL DEFAULT NULL,
  `reg_step` VARCHAR(16) NOT NULL DEFAULT 'lang',
  `age_confirmed` TINYINT(1) NOT NULL DEFAULT 0,
  `name` VARCHAR(80) NULL DEFAULT NULL,
  `photos` TEXT NULL COMMENT 'JSON: Telegram file_id lar (faqat file_id)',
  `gender` CHAR(1) NULL DEFAULT NULL COMMENT 'm yoki f',
  `region` TINYINT UNSIGNED NULL DEFAULT NULL,
  `interests` VARCHAR(255) NULL DEFAULT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT 'active | suspended',
  `premium_until` DATETIME NULL DEFAULT NULL,
  `state` VARCHAR(48) NULL DEFAULT NULL,
  `state_data` TEXT NULL,
  `card_nonce` CHAR(12) NULL DEFAULT NULL,
  `card_target` BIGINT NULL DEFAULT NULL,
  `card_ctx` VARCHAR(8) NULL DEFAULT NULL,
  `card_pos` INT NOT NULL DEFAULT 0,
  `search_pref` CHAR(1) NULL DEFAULT NULL,
  `active_chat_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `blocked_bot` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `last_seen_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_users_search` (`reg_step`, `status`, `gender`, `region`),
  KEY `idx_users_created` (`created_at`),
  KEY `idx_users_premium` (`premium_until`),
  KEY `idx_users_chat` (`active_chat_id`),
  KEY `idx_users_pick` (`reg_step`, `status`, `age_confirmed`, `gender`, `last_seen_at`),
  KEY `idx_users_seen` (`last_seen_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_processed_updates` (
  `update_id` BIGINT NOT NULL,
  `processed_at` DATETIME NOT NULL,
  PRIMARY KEY (`update_id`),
  KEY `idx_pu_time` (`processed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_failed_updates` (
  `update_id` BIGINT NOT NULL,
  `attempts` INT UNSIGNED NOT NULL DEFAULT 0,
  `last_error` VARCHAR(255) NULL DEFAULT NULL,
  `updated_at` DATETIME NOT NULL,
  PRIMARY KEY (`update_id`),
  KEY `idx_fu_time` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_outbox` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `dedupe_key` VARCHAR(120) NOT NULL,
  `chat_id` BIGINT NOT NULL,
  `method` VARCHAR(40) NOT NULL,
  `payload` MEDIUMTEXT NOT NULL,
  `priority` TINYINT UNSIGNED NOT NULL DEFAULT 5,
  `status` VARCHAR(10) NOT NULL DEFAULT 'pending' COMMENT 'pending | sending | sent | failed',
  `attempts` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  `next_attempt_at` DATETIME NOT NULL,
  `locked_until` DATETIME NULL DEFAULT NULL,
  `claim_token` CHAR(16) NULL DEFAULT NULL,
  `last_error` VARCHAR(255) NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_outbox_dedupe` (`dedupe_key`),
  KEY `idx_outbox_queue` (`status`, `next_attempt_at`, `priority`),
  KEY `idx_outbox_claim` (`claim_token`),
  KEY `idx_outbox_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_reactions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `from_id` BIGINT NOT NULL,
  `to_id` BIGINT NOT NULL,
  `kind` VARCHAR(8) NOT NULL COMMENT 'like | super | save',
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_reaction` (`from_id`, `to_id`, `kind`),
  KEY `idx_reaction_to` (`to_id`, `kind`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_seen` (
  `viewer_id` BIGINT NOT NULL,
  `target_id` BIGINT NOT NULL,
  `seen_at` DATETIME NOT NULL,
  PRIMARY KEY (`viewer_id`, `target_id`),
  KEY `idx_seen_time` (`seen_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_reg_msgs` (
  `user_id` BIGINT NOT NULL,
  `message_id` BIGINT NOT NULL,
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`user_id`, `message_id`),
  KEY `idx_reg_msgs_time` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_matches` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_a` BIGINT NOT NULL COMMENT 'kichik ID',
  `user_b` BIGINT NOT NULL COMMENT 'katta ID',
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_match_pair` (`user_a`, `user_b`),
  KEY `idx_match_b` (`user_b`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_chats` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `match_id` BIGINT UNSIGNED NOT NULL,
  `user_a` BIGINT NOT NULL,
  `user_b` BIGINT NOT NULL,
  `status` VARCHAR(8) NOT NULL DEFAULT 'active' COMMENT 'active | ended',
  `started_at` DATETIME NOT NULL,
  `ended_at` DATETIME NULL DEFAULT NULL,
  `ended_by` BIGINT NULL DEFAULT NULL,
  `end_reason` VARCHAR(16) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_chat_status` (`status`, `started_at`),
  KEY `idx_chat_match` (`match_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_reports` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `reporter_id` BIGINT NOT NULL,
  `reported_id` BIGINT NOT NULL,
  `chat_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `reason` VARCHAR(500) NOT NULL,
  `status` VARCHAR(10) NOT NULL DEFAULT 'open' COMMENT 'open | reviewed',
  `created_at` DATETIME NOT NULL,
  `reviewed_at` DATETIME NULL DEFAULT NULL,
  `reviewed_by` BIGINT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_report_status` (`status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_daily_limits` (
  `user_id` BIGINT NOT NULL,
  `day` DATE NOT NULL COMMENT 'UTC sana',
  `likes` INT UNSIGNED NOT NULL DEFAULT 0,
  `supers` INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`user_id`, `day`),
  KEY `idx_limits_day` (`day`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_products` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(32) NOT NULL,
  `kind` VARCHAR(8) NOT NULL COMMENT 'premium | boost',
  `days` INT UNSIGNED NOT NULL,
  `price_xtr` INT UNSIGNED NOT NULL,
  `active` TINYINT(1) NOT NULL DEFAULT 1,
  `sort` INT NOT NULL DEFAULT 0,
  `updated_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_product_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_orders` (
  `id` CHAR(32) NOT NULL,
  `user_id` BIGINT NOT NULL,
  `product_id` INT UNSIGNED NOT NULL,
  `kind` VARCHAR(8) NOT NULL,
  `audience` CHAR(1) NULL DEFAULT NULL,
  `days` INT UNSIGNED NOT NULL,
  `amount` INT UNSIGNED NOT NULL,
  `currency` CHAR(3) NOT NULL,
  `status` VARCHAR(10) NOT NULL DEFAULT 'pending' COMMENT 'pending | paid | expired',
  `telegram_payment_charge_id` VARCHAR(191) NULL DEFAULT NULL,
  `provider_payment_charge_id` VARCHAR(191) NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL,
  `expires_at` DATETIME NOT NULL,
  `paid_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_order_charge` (`telegram_payment_charge_id`),
  KEY `idx_order_user` (`user_id`, `status`),
  KEY `idx_order_status` (`status`, `expires_at`),
  KEY `idx_order_paid` (`paid_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_rejected_payments` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `order_id` VARCHAR(64) NULL DEFAULT NULL,
  `user_id` BIGINT NOT NULL,
  `amount` INT NULL DEFAULT NULL,
  `currency` VARCHAR(8) NULL DEFAULT NULL,
  `telegram_payment_charge_id` VARCHAR(191) NULL DEFAULT NULL,
  `reason` VARCHAR(64) NOT NULL,
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_rej_time` (`created_at`),
  KEY `idx_rej_charge` (`telegram_payment_charge_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_boosts` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `audience` CHAR(1) NOT NULL COMMENT 'f = ko‘proq qizlar ko‘rsin, m = ko‘proq yigitlar ko‘rsin',
  `order_id` CHAR(32) NOT NULL,
  `starts_at` DATETIME NOT NULL,
  `expires_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_boost_order` (`order_id`),
  KEY `idx_boost_active` (`audience`, `expires_at`, `starts_at`),
  KEY `idx_boost_user` (`user_id`, `expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_settings` (
  `name` VARCHAR(64) NOT NULL,
  `value` MEDIUMTEXT NOT NULL,
  `updated_at` DATETIME NOT NULL,
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_menu_aliases` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `label` VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `item_id` VARCHAR(16) NOT NULL COMMENT 'tugmaning ichki ID si',
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_alias_label` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_cards` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(64) NOT NULL,
  `last4` CHAR(4) NOT NULL COMMENT 'faqat oxirgi 4 raqam',
  `active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_card_last4` (`last4`, `active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_bank_pending` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `card_id` INT UNSIGNED NOT NULL,
  `amount_minor` BIGINT NOT NULL,
  `currency` CHAR(3) NOT NULL,
  `reference` VARCHAR(64) NULL DEFAULT NULL,
  `status` VARCHAR(10) NOT NULL DEFAULT 'pending' COMMENT 'pending | matched | expired | cancelled',
  `created_at` DATETIME NOT NULL,
  `expires_at` DATETIME NOT NULL,
  `matched_event_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_bp_status` (`status`, `expires_at`),
  KEY `idx_bp_card` (`card_id`, `status`, `amount_minor`),
  KEY `idx_bp_ref` (`reference`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_bank_events` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `source` VARCHAR(64) NOT NULL,
  `event_id` VARCHAR(128) NOT NULL,
  `amount_minor` BIGINT NOT NULL,
  `currency` CHAR(3) NOT NULL,
  `card_last4` CHAR(4) NULL DEFAULT NULL,
  `reference` VARCHAR(64) NULL DEFAULT NULL,
  `occurred_at` DATETIME NULL DEFAULT NULL,
  `received_at` DATETIME NOT NULL,
  `result` VARCHAR(10) NOT NULL COMMENT 'matched | unmatched | ambiguous',
  `pending_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_bank_event` (`source`, `event_id`),
  KEY `idx_be_time` (`received_at`),
  KEY `idx_be_result` (`result`, `received_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_broadcasts` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `admin_id` BIGINT NOT NULL,
  `text_uz` TEXT NOT NULL,
  `text_ru` TEXT NOT NULL,
  `text_en` TEXT NOT NULL,
  `status` VARCHAR(10) NOT NULL DEFAULT 'draft' COMMENT 'draft | queued | done | cancelled',
  `cursor_user_id` BIGINT NOT NULL DEFAULT 0,
  `enqueued` INT UNSIGNED NOT NULL DEFAULT 0,
  `cancel_reason` VARCHAR(64) NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL,
  `confirmed_at` DATETIME NULL DEFAULT NULL,
  `finished_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_bc_status` (`status`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_admin_audit` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `admin_id` BIGINT NOT NULL,
  `action` VARCHAR(64) NOT NULL,
  `target` VARCHAR(128) NULL DEFAULT NULL,
  `details` VARCHAR(500) NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_audit_time` (`created_at`),
  KEY `idx_audit_action` (`action`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_user_ext` (
  `user_id` BIGINT NOT NULL,
  `age` TINYINT UNSIGNED NULL DEFAULT NULL,
  `goal` VARCHAR(8) NULL DEFAULT NULL,
  `verified` TINYINT NOT NULL DEFAULT 0,
  `verified_at` DATETIME NULL DEFAULT NULL,
  `mod_hidden` TINYINT NOT NULL DEFAULT 0,
  `hidden_at` DATETIME NULL DEFAULT NULL,
  `pref_age_min` TINYINT UNSIGNED NULL DEFAULT NULL,
  `pref_age_max` TINYINT UNSIGNED NULL DEFAULT NULL,
  `pref_goal` VARCHAR(8) NULL DEFAULT NULL,
  `pref_verified` TINYINT NOT NULL DEFAULT 0,
  `updated_at` DATETIME NOT NULL,
  PRIMARY KEY (`user_id`),
  KEY `idx_ext_search` (`mod_hidden`, `age`),
  KEY `idx_ext_hidden` (`mod_hidden`, `hidden_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_verifications` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `file_id` VARCHAR(255) NOT NULL,
  `gesture` VARCHAR(16) NOT NULL,
  `status` VARCHAR(12) NOT NULL DEFAULT 'pending',
  `admin_id` BIGINT NULL DEFAULT NULL,
  `reason` VARCHAR(16) NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL,
  `decided_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ver_status` (`status`, `id`),
  KEY `idx_ver_user` (`user_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_like_msgs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `from_id` BIGINT NOT NULL,
  `to_id` BIGINT NOT NULL,
  `text` VARCHAR(1200) NOT NULL,
  `status` VARCHAR(12) NOT NULL,
  `reason` VARCHAR(16) NULL DEFAULT NULL,
  `admin_id` BIGINT NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL,
  `decided_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_lm_status` (`status`, `id`),
  KEY `idx_lm_pair` (`to_id`, `from_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_blocks` (
  `blocker_id` BIGINT NOT NULL,
  `blocked_id` BIGINT NOT NULL,
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`blocker_id`, `blocked_id`),
  KEY `idx_blocks_blocked` (`blocked_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_referrals` (
  `invited_id` BIGINT NOT NULL,
  `inviter_id` BIGINT NOT NULL,
  `created_at` DATETIME NOT NULL,
  `rewarded_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`invited_id`),
  KEY `idx_ref_inviter` (`inviter_id`, `rewarded_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_notices` (
  `user_id` BIGINT NOT NULL,
  `kind` VARCHAR(12) NOT NULL COMMENT 'likes | inactive',
  `sent_at` DATETIME NOT NULL,
  PRIMARY KEY (`user_id`, `kind`),
  KEY `idx_notice_time` (`kind`, `sent_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tb_profile_reviews` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `status` VARCHAR(10) NOT NULL DEFAULT 'pending' COMMENT 'pending | approved | hidden | cancelled',
  `admin_id` BIGINT NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL,
  `decided_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_pr_status` (`status`, `id`),
  KEY `idx_pr_user` (`user_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO `tb_products` (`code`, `kind`, `days`, `price_xtr`, `active`, `sort`, `updated_at`) VALUES
  ('premium_1',  'premium', 1,  25,  1, 1, UTC_TIMESTAMP()),
  ('premium_3',  'premium', 3,  60,  1, 2, UTC_TIMESTAMP()),
  ('premium_7',  'premium', 7,  120, 1, 3, UTC_TIMESTAMP()),
  ('premium_30', 'premium', 30, 350, 1, 4, UTC_TIMESTAMP()),
  ('boost',      'boost',   1,  30,  1, 10, UTC_TIMESTAMP());

INSERT IGNORE INTO `tb_settings` (`name`, `value`, `updated_at`) VALUES
  ('menu_version', '1', UTC_TIMESTAMP()),
  ('setup_closed', '0', UTC_TIMESTAMP()),
  ('schema_version', '3', UTC_TIMESTAMP()),
  ('likes_gate', '1', UTC_TIMESTAMP()),
  ('photo_review', '0', UTC_TIMESTAMP()),
  ('retention', '1', UTC_TIMESTAMP()),
  ('ref_reward_days', '1', UTC_TIMESTAMP()),
  ('ref_max_rewards', '30', UTC_TIMESTAMP()),
  ('age_min', '18', UTC_TIMESTAMP()),
  ('age_max', '99', UTC_TIMESTAMP()),
  ('likemsg_mode', 'on', UTC_TIMESTAMP()),
  ('likemsg_links', '1', UTC_TIMESTAMP()),
  ('likemsg_stopwords', '', UTC_TIMESTAMP()),
  ('verify_enabled', '1', UTC_TIMESTAMP()),
  ('autohide_reports', '3', UTC_TIMESTAMP()),
  ('autohide_days', '30', UTC_TIMESTAMP());
