-- Apply to an existing Hawk-AI MySQL 8 database once.

ALTER TABLE board_comments
    ADD COLUMN status ENUM('ACTIVE', 'HIDDEN', 'DELETED') NOT NULL DEFAULT 'ACTIVE' COMMENT '댓글 운영 상태' AFTER emoticon,
    ADD COLUMN moderated_by BIGINT UNSIGNED NULL COMMENT '마지막 조치 관리자 식별자' AFTER status,
    ADD COLUMN moderated_at DATETIME(6) NULL COMMENT '마지막 관리자 조치 일시' AFTER moderated_by,
    ADD COLUMN moderation_reason VARCHAR(500) NULL COMMENT '마지막 관리자 조치 사유' AFTER moderated_at,
    ADD KEY ix_board_comments_moderation (status, created_at DESC),
    ADD CONSTRAINT fk_board_comments_moderated_by FOREIGN KEY (moderated_by) REFERENCES users (id) ON DELETE SET NULL;

UPDATE board_comments
SET status = 'DELETED'
WHERE deleted_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS comment_moderation_logs (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '댓글 조치 이력 식별자',
    comment_id      BIGINT UNSIGNED NOT NULL COMMENT '대상 댓글 식별자',
    moderator_id    BIGINT UNSIGNED NULL COMMENT '조치 관리자 식별자',
    action          ENUM('HIDE', 'RESTORE', 'DELETE') NOT NULL COMMENT '관리 조치',
    previous_status ENUM('ACTIVE', 'HIDDEN', 'DELETED') NOT NULL COMMENT '조치 전 상태',
    next_status     ENUM('ACTIVE', 'HIDDEN', 'DELETED') NOT NULL COMMENT '조치 후 상태',
    reason          VARCHAR(500) NOT NULL COMMENT '관리자 조치 사유',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '조치 일시',
    PRIMARY KEY (id),
    KEY ix_comment_moderation_logs_comment (comment_id, created_at DESC),
    KEY ix_comment_moderation_logs_moderator (moderator_id, created_at DESC),
    CONSTRAINT fk_comment_moderation_logs_comment FOREIGN KEY (comment_id) REFERENCES board_comments (id) ON DELETE CASCADE,
    CONSTRAINT fk_comment_moderation_logs_moderator FOREIGN KEY (moderator_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='관리자 댓글 조치 감사 이력';
