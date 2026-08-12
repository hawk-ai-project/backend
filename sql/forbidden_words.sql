-- Apply once to an existing Hawk-AI MySQL 8 database.
CREATE TABLE IF NOT EXISTS forbidden_words (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    word VARCHAR(100) NOT NULL,
    normalized_word VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id), UNIQUE KEY uq_forbidden_words_normalized (normalized_word),
    KEY ix_forbidden_words_active (is_active, id),
    CONSTRAINT fk_forbidden_words_created_by FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='관리자 설정 금칙어';

CREATE TABLE IF NOT EXISTS content_moderation_flags (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    forbidden_word_id BIGINT UNSIGNED NOT NULL,
    content_type ENUM('BOARD', 'COMMENT') NOT NULL,
    content_id BIGINT UNSIGNED NOT NULL,
    matched_text VARCHAR(100) NOT NULL,
    excerpt VARCHAR(500) NOT NULL,
    status ENUM('OPEN', 'RESOLVED', 'DISMISSED') NOT NULL DEFAULT 'OPEN',
    resolved_by BIGINT UNSIGNED NULL,
    resolved_at DATETIME(6) NULL,
    resolution_note VARCHAR(500) NULL,
    detected_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_content_moderation_flag (forbidden_word_id, content_type, content_id),
    KEY ix_content_moderation_flags_status (status, detected_at DESC),
    KEY ix_content_moderation_flags_content (content_type, content_id),
    CONSTRAINT fk_content_flags_word FOREIGN KEY (forbidden_word_id) REFERENCES forbidden_words (id) ON DELETE CASCADE,
    CONSTRAINT fk_content_flags_resolved_by FOREIGN KEY (resolved_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='게시글·댓글 금칙어 탐지 결과';
