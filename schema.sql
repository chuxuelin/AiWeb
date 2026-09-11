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
  `nickname`      VARCHAR(50)  DEFAULT NULL COMMENT '个人昵称',
  `bio`           VARCHAR(255) DEFAULT NULL COMMENT '个人简介',
  `gender`        VARCHAR(10)  DEFAULT NULL COMMENT '性别',
  `birthday`      DATE         DEFAULT NULL COMMENT '生日',
  `country`       VARCHAR(50)  DEFAULT NULL COMMENT '国家',
  `region`        VARCHAR(100) DEFAULT NULL COMMENT '地区',
  `signature`     VARCHAR(255) DEFAULT NULL COMMENT '个性签名',
  `email`         VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
  `level`         VARCHAR(20)  NOT NULL DEFAULT '普通用户' COMMENT '用户等级',
  `avatar`        LONGTEXT     DEFAULT NULL COMMENT '头像图片 Data URL',
  `oauth_provider` VARCHAR(20)  DEFAULT NULL COMMENT '第三方平台: wechat/qq',
  `oauth_id`      VARCHAR(100) DEFAULT NULL COMMENT '第三方平台用户唯一 ID',
  `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_username` (`username`),
  UNIQUE KEY `uk_users_oauth` (`oauth_provider`, `oauth_id`)
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

-- ------------------------------------------------------------
-- 运动记录表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `exercise_logs` (
  `id`               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`          INT UNSIGNED NOT NULL,
  `exercise_type`    VARCHAR(50) NOT NULL COMMENT '运动项目',
  `duration_minutes` INT UNSIGNED NOT NULL COMMENT '运动时长(分钟)',
  `energy_kcal`      INT UNSIGNED NOT NULL COMMENT '消耗能量(KCAL)',
  `record_date`      DATE NOT NULL COMMENT '运动日期',
  `created_at`       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_exercise_user_date` (`user_id`, `record_date`),
  CONSTRAINT `fk_exercise_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='运动记录';

-- ------------------------------------------------------------
-- 运动社区：帖子、评论、点赞
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `community_posts` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    INT UNSIGNED NOT NULL,
  `content`    TEXT NOT NULL COMMENT '帖子内容',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_posts_created` (`created_at`),
  CONSTRAINT `fk_posts_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='运动社区帖子';

CREATE TABLE IF NOT EXISTS `community_comments` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `post_id`    INT UNSIGNED NOT NULL,
  `user_id`    INT UNSIGNED NOT NULL,
  `content`    VARCHAR(500) NOT NULL COMMENT '评论内容',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_comments_post` (`post_id`),
  CONSTRAINT `fk_comments_post` FOREIGN KEY (`post_id`) REFERENCES `community_posts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_comments_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='运动社区评论';

CREATE TABLE IF NOT EXISTS `community_likes` (
  `post_id`    INT UNSIGNED NOT NULL,
  `user_id`    INT UNSIGNED NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`post_id`, `user_id`),
  CONSTRAINT `fk_likes_post` FOREIGN KEY (`post_id`) REFERENCES `community_posts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_likes_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='运动社区点赞';

CREATE TABLE IF NOT EXISTS `community_follows` (
  `follower_id`  INT UNSIGNED NOT NULL COMMENT '关注者',
  `following_id` INT UNSIGNED NOT NULL COMMENT '被关注者',
  `created_at`   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`follower_id`, `following_id`),
  CONSTRAINT `fk_follows_follower` FOREIGN KEY (`follower_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_follows_following` FOREIGN KEY (`following_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='运动社区关注关系';
