-- ============================================================================
-- Tanishuv bot — upgrade_v3.sql (schema 2 -> 3)
-- Avval o'rnatilgan bot uchun: bloklar, referal, eslatmalar, anketa moderatsiyasi, indekslar.
-- Takror import qilsa xavfsiz (CREATE ... IF NOT EXISTS, INSERT IGNORE).
-- Indekslar uchun MariaDB 10.1.4+ kerak. MySQL 8 da "ADD INDEX IF NOT EXISTS" yo'q:
-- u holda oxirgi ikki ALTER qatorini bir marta qo'lda ishga tushiring (xato bersa — indeks bor).
-- ============================================================================

SET NAMES utf8mb4;
SET time_zone = '+00:00';

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

INSERT IGNORE INTO `tb_settings` (`name`, `value`, `updated_at`) VALUES
  ('likes_gate', '1', UTC_TIMESTAMP()),
  ('photo_review', '0', UTC_TIMESTAMP()),
  ('retention', '1', UTC_TIMESTAMP()),
  ('ref_reward_days', '1', UTC_TIMESTAMP()),
  ('ref_max_rewards', '30', UTC_TIMESTAMP());

UPDATE `tb_settings` SET `value` = '3', `updated_at` = UTC_TIMESTAMP() WHERE `name` = 'schema_version' AND `value` < '3';

ALTER TABLE `tb_users` ADD INDEX IF NOT EXISTS `idx_users_pick` (`reg_step`, `status`, `age_confirmed`, `gender`, `last_seen_at`);
ALTER TABLE `tb_users` ADD INDEX IF NOT EXISTS `idx_users_seen` (`last_seen_at`);
