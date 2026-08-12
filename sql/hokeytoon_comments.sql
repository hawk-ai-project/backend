CREATE TABLE IF NOT EXISTS hokeytoon_comments (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    episode_id          TINYINT UNSIGNED NOT NULL,
    author_id           BIGINT UNSIGNED NOT NULL,
    parent_comment_id   BIGINT UNSIGNED NULL,
    content             VARCHAR(1000) NOT NULL DEFAULT '',
    emoticon            VARCHAR(40) NULL,
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    deleted_at          DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_hokeytoon_comments_episode_id (episode_id, id),
    KEY ix_hokeytoon_comments_thread (episode_id, parent_comment_id, deleted_at, created_at, id),
    KEY ix_hokeytoon_comments_author (author_id, deleted_at, created_at DESC),
    CONSTRAINT ck_hokeytoon_episode CHECK (episode_id BETWEEN 1 AND 10),
    CONSTRAINT ck_hokeytoon_comment_body CHECK (CHAR_LENGTH(TRIM(content)) > 0 OR emoticon IS NOT NULL),
    CONSTRAINT fk_hokeytoon_comments_author FOREIGN KEY (author_id) REFERENCES users (id),
    CONSTRAINT fk_hokeytoon_comments_parent FOREIGN KEY (episode_id, parent_comment_id)
        REFERENCES hokeytoon_comments (episode_id, id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='호키툰 회차 댓글과 대댓글';
