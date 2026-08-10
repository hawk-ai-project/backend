CREATE TABLE IF NOT EXISTS system_settings (
    setting_key    VARCHAR(100) NOT NULL,
    setting_value  VARCHAR(1000) NOT NULL,
    updated_by     BIGINT UNSIGNED NULL,
    updated_at     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (setting_key),
    CONSTRAINT fk_system_settings_updated_by FOREIGN KEY (updated_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO system_settings (setting_key, setting_value) VALUES
    ('signup_enabled', 'true'),
    ('board_write_enabled', 'true'),
    ('inspection_notification_enabled', 'false'),
    ('session_expire_minutes', '30')
ON DUPLICATE KEY UPDATE setting_key = VALUES(setting_key);
