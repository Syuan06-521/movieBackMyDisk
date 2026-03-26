-- MySQL 数据库初始化脚本
-- film_transfer 数据库

-- 创建数据库
CREATE DATABASE IF NOT EXISTS film_transfer
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_unicode_ci;

USE film_transfer;

-- ============================================
-- 用户管理相关表
-- ============================================

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    role ENUM('admin', 'user', 'viewer') DEFAULT 'user',
    status ENUM('active', 'inactive', 'banned') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    INDEX idx_username (username),
    INDEX idx_role (role),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 操作日志表
CREATE TABLE IF NOT EXISTS operation_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSON,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    status ENUM('success', 'failure') DEFAULT 'success',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 影视目录相关表
-- ============================================

-- 影视目录条目表
CREATE TABLE IF NOT EXISTS catalog_items (
    id VARCHAR(100) NOT NULL,
    addon_name VARCHAR(100) NOT NULL,
    item_type ENUM('movie', 'series') NOT NULL,
    name VARCHAR(255),
    year INT,
    imdb_id VARCHAR(50),
    poster VARCHAR(500),
    raw_meta JSON,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, addon_name),
    INDEX idx_item_type (item_type),
    INDEX idx_year (year),
    INDEX idx_first_seen (first_seen)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 转存任务表
CREATE TABLE IF NOT EXISTS transfer_tasks (
    task_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    catalog_item_id VARCHAR(100) NOT NULL,
    addon_name VARCHAR(100) NOT NULL,
    status ENUM('pending', 'searching', 'found', 'saving', 'done', 'failed', 'skipped', 'pending_manual') NOT NULL DEFAULT 'pending',
    resource_name TEXT,
    resource_url VARCHAR(500),
    resolution VARCHAR(20),
    size_gb DECIMAL(10,2),
    codec VARCHAR(20),
    quark_share_id VARCHAR(100),
    quark_save_path VARCHAR(500),
    error_msg TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_catalog_item (catalog_item_id, addon_name),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 插件快照表
CREATE TABLE IF NOT EXISTS addon_snapshots (
    addon_name VARCHAR(100) NOT NULL,
    catalog_id VARCHAR(100) NOT NULL,
    snapshot_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    item_count INT,
    PRIMARY KEY (addon_name, catalog_id),
    INDEX idx_snapshot_at (snapshot_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 同步历史表
-- ============================================

-- 同步历史记录表
CREATE TABLE IF NOT EXISTS sync_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    item_id VARCHAR(100) NOT NULL,
    addon_name VARCHAR(100) NOT NULL,
    item_name VARCHAR(255),
    item_type ENUM('movie', 'series'),
    resource_title VARCHAR(500),
    resource_url VARCHAR(500),
    save_path VARCHAR(500),
    resolution VARCHAR(20),
    size_gb DECIMAL(10,2),
    codec VARCHAR(20),
    status ENUM('saved', 'skipped', 'failed', 'pending_manual') NOT NULL,
    sync_date DATE NOT NULL,
    sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_reason TEXT,
    tried_resources JSON,
    attempted_paths JSON,
    INDEX idx_item_id (item_id, addon_name),
    INDEX idx_sync_date (sync_date),
    INDEX idx_status (status),
    INDEX idx_item_type (item_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 失败记录表
CREATE TABLE IF NOT EXISTS failed_transfers (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    item_id VARCHAR(100) NOT NULL,
    addon_name VARCHAR(100) NOT NULL,
    item_name VARCHAR(255),
    item_type ENUM('movie', 'series'),
    attempted_paths JSON,
    error_reason TEXT,
    tried_resources JSON,
    failed_date DATE NOT NULL,
    failed_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_item_id (item_id, addon_name),
    INDEX idx_failed_date (failed_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 系统配置表
-- ============================================

-- 系统设置表
CREATE TABLE IF NOT EXISTS system_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT,
    setting_type ENUM('string', 'number', 'boolean', 'json') DEFAULT 'string',
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_key (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 初始数据
-- ============================================

-- 插入默认管理员账户（密码：admin123，使用 bcrypt 加密）
-- 注意：实际密码哈希需要在应用层使用 passlib 生成
INSERT INTO users (username, password_hash, email, role, status)
VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzS3MebAJu', 'admin@example.com', 'admin', 'active')
ON DUPLICATE KEY UPDATE username=username;

-- 插入默认系统设置
INSERT INTO system_settings (setting_key, setting_value, setting_type, description) VALUES
('quark_cookie', '', 'string', '夸克网盘 Cookie'),
('save_folders', '["filmTransfer"]', 'json', '保存文件夹列表'),
('auto_create_folder', 'true', 'boolean', '自动创建文件夹'),
('check_interval_minutes', '60', 'number', '检查间隔（分钟）'),
('max_results_per_site', '15', 'number', '每个站点最大结果数'),
('preferred_resolutions', '["2160p", "1080p", "720p"]', 'json', '优选分辨率'),
('min_resolution', '720p', 'string', '最低分辨率'),
('min_size_gb', '0.5', 'number', '最小文件大小 GB'),
('max_size_gb', '60', 'number', '最大文件大小 GB'),
('preferred_codecs', '["HEVC", "H265", "H264", "AVC"]', 'json', '优选编码'),
('notification_enabled', 'false', 'boolean', '通知开关'),
('notification_type', 'bark', 'string', '通知类型')
ON DUPLICATE KEY UPDATE setting_key=setting_key;
