-- ============================================================
-- MoveWell 运动健康后台  MySQL 数据库结构
-- 数据库: health_app   字符集: utf8mb4   引擎: InnoDB
-- 用法: mysql -u root -p < schema.sql
--   或: python init_db.py  (自动建库建表并写入初始数据)
-- ============================================================

CREATE DATABASE IF NOT EXISTS `health_app`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `health_app`;

-- ------------------------------------------------------------
-- 用户表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username`      VARCHAR(50)  NOT NULL COMMENT '登录账号',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希(werkzeug)',
  `name`          VARCHAR(50)  NOT NULL COMMENT '昵称',
  `email`         VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
  `level`         VARCHAR(20)  NOT NULL DEFAULT '普通用户' COMMENT '用户等级',
  `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ------------------------------------------------------------
-- 每日健康记录表 (每个用户每天一条, 含各项指标/hero/体适能评分)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `daily_health` (
  `id`              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`         INT UNSIGNED NOT NULL,
  `record_date`     DATE         NOT NULL COMMENT '记录日期',
  `steps`           INT          NOT NULL DEFAULT 0    COMMENT '步数',
  `heart_rate`      INT          NOT NULL DEFAULT 0    COMMENT '心率 BPM',
  `sleep_hours`     DECIMAL(4,1) NOT NULL DEFAULT 0.0  COMMENT '睡眠时长 h',
  `calories`        INT          NOT NULL DEFAULT 0    COMMENT '热量消耗 KCAL',
  `water_liters`    DECIMAL(4,1) NOT NULL DEFAULT 0.0  COMMENT '水分摄入 L',
  `sleep_quality`   INT          NOT NULL DEFAULT 0    COMMENT '睡眠质量 %',
  `exercise_minutes` INT         NOT NULL DEFAULT 0    COMMENT '运动时长 min',
  `fitness_score`   INT          NOT NULL DEFAULT 0    COMMENT '体适能评分 %(一周趋势图)',
  `summary_message` VARCHAR(500) DEFAULT NULL          COMMENT '体适能分析文案',
  `created_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_date` (`user_id`, `record_date`),
  CONSTRAINT `fk_daily_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日健康记录表';

-- ------------------------------------------------------------
-- 健康提醒任务表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `health_tasks` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    INT UNSIGNED NOT NULL,
  `title`      VARCHAR(100) NOT NULL COMMENT '任务标题',
  `detail`     VARCHAR(255) DEFAULT NULL COMMENT '任务详情',
  `status`     VARCHAR(20)  NOT NULL DEFAULT '正常'  COMMENT '状态文字',
  `tone`       VARCHAR(20)  NOT NULL DEFAULT 'normal' COMMENT '色调: normal/warning/danger',
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_tasks_user` (`user_id`),
  CONSTRAINT `fk_tasks_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='健康提醒任务表';

-- ------------------------------------------------------------
-- 健康分析/建议表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `health_insights` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    INT UNSIGNED NOT NULL,
  `title`      VARCHAR(100) NOT NULL COMMENT '标题, 如: 综合评估/建议',
  `text`       VARCHAR(1000) NOT NULL COMMENT '分析内容',
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_insights_user` (`user_id`),
  CONSTRAINT `fk_insights_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='健康分析建议表';
