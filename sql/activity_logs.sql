-- Apply this migration to an existing Hawk-AI MySQL 8.0.16+ database.
-- Request bodies, passwords, access tokens, and query values are intentionally excluded.

CREATE TABLE IF NOT EXISTS activity_logs (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '활동 로그 고유 식별자',
    request_id      CHAR(36) NOT NULL COMMENT '요청 단위 추적 UUID',
    user_id         BIGINT UNSIGNED NULL COMMENT '인증된 사용자 식별자',
    session_id      CHAR(36) NULL COMMENT '인증 세션 UUID; 토큰 원문은 저장하지 않음',
    category        VARCHAR(30) NOT NULL COMMENT 'AUTH, BOARD, INSPECTION, ADMIN 등 활동 분류',
    action          VARCHAR(80) NOT NULL COMMENT 'LOGIN, BOARD_CREATE 등 정규화된 활동명',
    http_method     VARCHAR(10) NOT NULL COMMENT 'HTTP 요청 메서드',
    path            VARCHAR(500) NOT NULL COMMENT '민감한 쿼리 값을 제외한 요청 경로',
    route_template  VARCHAR(500) NULL COMMENT 'FastAPI 라우트 템플릿',
    status_code     SMALLINT UNSIGNED NOT NULL COMMENT 'HTTP 응답 상태 코드',
    outcome         ENUM('SUCCESS', 'DENIED', 'FAILURE') NOT NULL COMMENT '요청 처리 결과',
    severity        ENUM('INFO', 'WARNING', 'ERROR') NOT NULL DEFAULT 'INFO' COMMENT '운영 심각도',
    duration_ms     INT UNSIGNED NOT NULL COMMENT '서버 요청 처리 시간(ms)',
    ip_address      VARCHAR(45) NULL COMMENT '요청 클라이언트 IPv4 또는 IPv6',
    user_agent      VARCHAR(500) NULL COMMENT '요청 User-Agent',
    metadata        JSON NULL COMMENT '본문과 비밀정보를 제외한 추가 추적 정보',
    occurred_at     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '활동 발생 일시(UTC)',
    PRIMARY KEY (id),
    UNIQUE KEY uq_activity_logs_request_id (request_id),
    KEY ix_activity_logs_occurred (occurred_at DESC, id DESC),
    KEY ix_activity_logs_user_occurred (user_id, occurred_at DESC),
    KEY ix_activity_logs_outcome_occurred (outcome, occurred_at DESC),
    KEY ix_activity_logs_category_action (category, action, occurred_at DESC),
    KEY ix_activity_logs_status_occurred (status_code, occurred_at DESC),
    CONSTRAINT ck_activity_logs_status CHECK (status_code BETWEEN 100 AND 599),
    CONSTRAINT fk_activity_logs_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='관리자 감사 및 사용자 활동 모니터링 로그';

-- Recommended scheduled retention job (run after exporting logs required by policy):
-- DELETE FROM activity_logs WHERE occurred_at < UTC_TIMESTAMP() - INTERVAL 180 DAY LIMIT 10000;
