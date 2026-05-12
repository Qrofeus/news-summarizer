CREATE DATABASE IF NOT EXISTS qrofeus_news CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE qrofeus_news;

CREATE TABLE IF NOT EXISTS news_recipients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    active BOOLEAN DEFAULT 1,
    timezone VARCHAR(50) DEFAULT 'America/Los_Angeles',
    preferences JSON DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active (active)
) ENGINE=InnoDB;

INSERT IGNORE INTO news_recipients (email) VALUES ('admin@qrofeus.dev');

CREATE TABLE IF NOT EXISTS execution_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    articles_scraped INT,
    emails_sent INT,
    errors TEXT,
    execution_duration_seconds FLOAT,
    INDEX idx_execution_time (execution_time)
) ENGINE=InnoDB;
