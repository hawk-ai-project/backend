-- Apply this migration to an existing Hawk-AI MySQL 8.0.16+ database.
-- A NULL parent_comment_id represents a top-level comment.
-- A non-NULL parent_comment_id represents a reply on the same board.

CREATE TABLE IF NOT EXISTS board_comments (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '댓글 고유 식별자',
    board_id            BIGINT UNSIGNED NOT NULL COMMENT '댓글이 작성된 게시글 식별자',
    author_id           BIGINT UNSIGNED NOT NULL COMMENT '댓글 작성자 식별자',
    parent_comment_id   BIGINT UNSIGNED NULL COMMENT '대댓글이 답변하는 부모 댓글 식별자; NULL이면 최상위 댓글',
    content             TEXT NOT NULL COMMENT '댓글 본문',
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '댓글 생성 일시',
    updated_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '댓글 수정 일시',
    deleted_at          DATETIME(6) NULL COMMENT '소프트 삭제 일시',
    PRIMARY KEY (id),
    UNIQUE KEY uq_board_comments_board_id (board_id, id),
    KEY ix_board_comments_thread (board_id, parent_comment_id, deleted_at, created_at, id),
    KEY ix_board_comments_author (author_id, deleted_at, created_at DESC),
    CONSTRAINT ck_board_comments_content CHECK (CHAR_LENGTH(TRIM(content)) BETWEEN 1 AND 2000),
    CONSTRAINT fk_board_comments_board FOREIGN KEY (board_id) REFERENCES boards (id) ON DELETE CASCADE,
    CONSTRAINT fk_board_comments_author FOREIGN KEY (author_id) REFERENCES users (id),
    CONSTRAINT fk_board_comments_parent FOREIGN KEY (board_id, parent_comment_id)
        REFERENCES board_comments (board_id, id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='게시글 댓글 및 대댓글 정보';
