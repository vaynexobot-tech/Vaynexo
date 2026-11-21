-- ============================================================================
-- Tanishuv bot — upgrade.sql (FAQAT avval o‘rnatilgan bot uchun)
--
-- Agar siz botning OLDINGI versiyasini o‘rnatib, database.sql yoki migration.sql ni
-- allaqachon import qilgan bo‘lsangiz, faqat shu faylni import qiling.
-- U faqat yangi jadvallarni (CREATE TABLE IF NOT EXISTS) va yangi sozlamalarni
-- (INSERT IGNORE) qo‘shadi. DROP, ALTER, DELETE, UPDATE yo‘q. Mavjud ma’lumotga tegmaydi.
-- Bir necha marta import qilinsa ham xavfsiz.
--
-- Yangi o‘rnatish bo‘lsa bu fayl KERAK EMAS — database.sql ni import qiling.
-- ============================================================================

SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE TABLE IF NOT EXISTS `tb_reg_msgs` (
  `user_id` BIGINT NOT NULL,
  `message_id` BIGINT NOT NULL,
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`user_id`, `message_id`),
  KEY `idx_reg_msgs_time` (`created_at`)
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

INSERT IGNORE INTO `tb_settings` (`name`, `value`, `updated_at`) VALUES
  ('menu_version', '1', UTC_TIMESTAMP()),
  ('setup_closed', '0', UTC_TIMESTAMP()),
  ('schema_version', '2', UTC_TIMESTAMP()),
  ('age_min', '18', UTC_TIMESTAMP()),
  ('age_max', '99', UTC_TIMESTAMP()),
  ('likemsg_mode', 'on', UTC_TIMESTAMP()),
  ('likemsg_links', '1', UTC_TIMESTAMP()),
  ('likemsg_stopwords', '', UTC_TIMESTAMP()),
  ('verify_enabled', '1', UTC_TIMESTAMP()),
  ('autohide_reports', '3', UTC_TIMESTAMP()),
  ('autohide_days', '30', UTC_TIMESTAMP());
