-- Hawk-AI 전체 데이터베이스 스키마
-- 대상: MySQL 8.0.16+ / InnoDB / utf8mb4
-- 실행 예: mysql -u <user> -p <database> < backend/sql/schema.sql
--
-- 설계 기준
-- 1. 비밀번호 원문과 JWT secret은 저장하지 않는다. password_hash와 세션 토큰 hash만 저장한다.
-- 2. 이미지 파일 자체는 객체 스토리지/파일 서버에 두고, DB에는 storage_key와 메타데이터만 저장한다.
-- 3. 한 점검에서 AI 분석을 재실행할 수 있으므로 inspection -> detection_run -> detection 구조로 분리한다.
-- 4. 통계는 inspections, detections, inspection_actions를 집계해 산출하며 중복 통계 테이블은 두지 않는다.
-- 5. frontend의 localStorage 게시글 임시 저장은 서버 데이터가 아니므로 이 스키마에 포함하지 않는다.
-- 6. 기존 question은 예제 도메인이므로 포함하지 않으며, detection_log는 detection_runs/detections로 대체한다.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;
SET time_zone = '+00:00';

-- ---------------------------------------------------------------------------
-- 사용자와 인증
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS roles (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code            VARCHAR(30) NOT NULL,
    name            VARCHAR(50) NOT NULL,
    description     VARCHAR(255) NULL,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_roles_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS users (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    role_id         BIGINT UNSIGNED NOT NULL,
    email           VARCHAR(254) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL COMMENT 'Argon2id 또는 bcrypt 해시',
    name            VARCHAR(100) NOT NULL,
    status          ENUM('PENDING', 'ACTIVE', 'SUSPENDED', 'WITHDRAWN') NOT NULL DEFAULT 'ACTIVE',
    last_login_at   DATETIME(6) NULL,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    deleted_at      DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email),
    KEY ix_users_role_status (role_id, status),
    CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS auth_sessions (
    id                  CHAR(36) NOT NULL COMMENT 'JWT sid claim에 넣는 UUID',
    user_id             BIGINT UNSIGNED NOT NULL,
    refresh_token_hash  CHAR(64) NULL COMMENT 'refresh token을 사용할 때 SHA-256 hash만 저장',
    user_agent          VARCHAR(500) NULL,
    ip_address          VARCHAR(45) NULL,
    expires_at          DATETIME(6) NOT NULL,
    last_used_at        DATETIME(6) NULL,
    revoked_at          DATETIME(6) NULL,
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_auth_sessions_refresh_hash (refresh_token_hash),
    KEY ix_auth_sessions_user_active (user_id, revoked_at, expires_at),
    CONSTRAINT fk_auth_sessions_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 현재 backend/sql/menu.sql API와의 호환을 위한 서비스 메뉴.
CREATE TABLE IF NOT EXISTS menu (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    parent_id       BIGINT UNSIGNED NULL,
    name            VARCHAR(100) NOT NULL,
    path            VARCHAR(255) NOT NULL,
    icon            VARCHAR(100) NULL,
    menu_type       ENUM('GROUP', 'PAGE', 'ACTION') NOT NULL DEFAULT 'PAGE',
    description     VARCHAR(500) NULL,
    is_use          BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INT NOT NULL DEFAULT 0,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_menu_path (path),
    KEY ix_menu_active_order (is_use, sort_order),
    KEY ix_menu_parent_order (parent_id, sort_order),
    CONSTRAINT fk_menu_parent FOREIGN KEY (parent_id) REFERENCES menu (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 점검 위치와 현장 점검
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS locations (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name            VARCHAR(150) NOT NULL,
    address         VARCHAR(500) NULL,
    latitude        DECIMAL(10, 7) NULL,
    longitude       DECIMAL(10, 7) NULL,
    description     VARCHAR(1000) NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      BIGINT UNSIGNED NOT NULL,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_locations_name (name),
    KEY ix_locations_coordinates (latitude, longitude),
    CONSTRAINT ck_locations_latitude CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CONSTRAINT ck_locations_longitude CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    CONSTRAINT fk_locations_created_by FOREIGN KEY (created_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS inspections (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    location_id         BIGINT UNSIGNED NULL,
    inspector_id        BIGINT UNSIGNED NOT NULL,
    reviewer_id         BIGINT UNSIGNED NULL,
    title               VARCHAR(200) NOT NULL,
    notes               TEXT NULL COMMENT '점검자가 작성한 현장 메모',
    ai_opinion          TEXT NULL COMMENT 'LLM이 생성한 점검 의견',
    status              ENUM('DRAFT', 'ANALYZING', 'REVIEW_REQUIRED', 'ACTION_REQUIRED', 'RESOLVED', 'FAILED') NOT NULL DEFAULT 'DRAFT',
    priority            ENUM('LOW', 'MEDIUM', 'HIGH', 'URGENT') NOT NULL DEFAULT 'MEDIUM',
    captured_at         DATETIME(6) NOT NULL,
    reviewed_at         DATETIME(6) NULL,
    resolved_at         DATETIME(6) NULL,
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    deleted_at          DATETIME(6) NULL,
    PRIMARY KEY (id),
    KEY ix_inspections_history (captured_at DESC, id DESC),
    KEY ix_inspections_status_date (status, captured_at DESC),
    KEY ix_inspections_location_date (location_id, captured_at DESC),
    KEY ix_inspections_inspector_date (inspector_id, captured_at DESC),
    CONSTRAINT fk_inspections_location FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE SET NULL,
    CONSTRAINT fk_inspections_inspector FOREIGN KEY (inspector_id) REFERENCES users (id),
    CONSTRAINT fk_inspections_reviewer FOREIGN KEY (reviewer_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS inspection_images (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    inspection_id   BIGINT UNSIGNED NOT NULL,
    kind            ENUM('ORIGINAL', 'ANNOTATED') NOT NULL DEFAULT 'ORIGINAL',
    storage_key     VARCHAR(1024) NOT NULL COMMENT '버킷 내부 key; 만료 가능한 공개 URL 저장 금지',
    original_name   VARCHAR(255) NULL,
    mime_type       VARCHAR(100) NOT NULL,
    byte_size       BIGINT UNSIGNED NOT NULL,
    width           INT UNSIGNED NULL,
    height          INT UNSIGNED NULL,
    sha256          CHAR(64) NULL,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_inspection_images_storage_key (storage_key),
    KEY ix_inspection_images_inspection_kind (inspection_id, kind),
    CONSTRAINT ck_inspection_images_byte_size CHECK (byte_size > 0),
    CONSTRAINT ck_inspection_images_dimensions CHECK ((width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)),
    CONSTRAINT fk_inspection_images_inspection FOREIGN KEY (inspection_id) REFERENCES inspections (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- AI 분석과 객체 탐지
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS waste_types (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code            VARCHAR(50) NOT NULL COMMENT '모델 class code',
    name_ko         VARCHAR(100) NOT NULL,
    name_en         VARCHAR(100) NULL,
    description     VARCHAR(500) NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_waste_types_code (code),
    UNIQUE KEY uq_waste_types_name_ko (name_ko)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS detection_runs (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    inspection_id       BIGINT UNSIGNED NOT NULL,
    source_image_id     BIGINT UNSIGNED NOT NULL,
    annotated_image_id  BIGINT UNSIGNED NULL,
    model_name          VARCHAR(100) NOT NULL,
    model_version       VARCHAR(100) NOT NULL,
    status              ENUM('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED') NOT NULL DEFAULT 'QUEUED',
    inference_ms        INT UNSIGNED NULL,
    raw_result          JSON NULL COMMENT '모델 원본 응답 보존용; 검색 필드는 detections에 정규화',
    error_message       TEXT NULL,
    started_at          DATETIME(6) NULL,
    completed_at        DATETIME(6) NULL,
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_detection_runs_inspection (inspection_id, created_at DESC),
    KEY ix_detection_runs_status_created (status, created_at),
    CONSTRAINT ck_detection_runs_time CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at),
    CONSTRAINT fk_detection_runs_inspection FOREIGN KEY (inspection_id) REFERENCES inspections (id) ON DELETE CASCADE,
    CONSTRAINT fk_detection_runs_source_image FOREIGN KEY (source_image_id) REFERENCES inspection_images (id),
    CONSTRAINT fk_detection_runs_annotated_image FOREIGN KEY (annotated_image_id) REFERENCES inspection_images (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS detections (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    detection_run_id BIGINT UNSIGNED NOT NULL,
    waste_type_id   BIGINT UNSIGNED NOT NULL,
    confidence      DECIMAL(6, 5) NOT NULL,
    bbox_x          DECIMAL(8, 7) NOT NULL COMMENT '0~1 정규화 좌상단 x',
    bbox_y          DECIMAL(8, 7) NOT NULL COMMENT '0~1 정규화 좌상단 y',
    bbox_width      DECIMAL(8, 7) NOT NULL COMMENT '0~1 정규화 너비',
    bbox_height     DECIMAL(8, 7) NOT NULL COMMENT '0~1 정규화 높이',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_detections_run_type (detection_run_id, waste_type_id),
    KEY ix_detections_type_created (waste_type_id, created_at),
    CONSTRAINT ck_detections_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT ck_detections_bbox CHECK (
        bbox_x BETWEEN 0 AND 1 AND bbox_y BETWEEN 0 AND 1
        AND bbox_width > 0 AND bbox_width <= 1
        AND bbox_height > 0 AND bbox_height <= 1
        AND bbox_x + bbox_width <= 1.0000001
        AND bbox_y + bbox_height <= 1.0000001
    ),
    CONSTRAINT fk_detections_run FOREIGN KEY (detection_run_id) REFERENCES detection_runs (id) ON DELETE CASCADE,
    CONSTRAINT fk_detections_waste_type FOREIGN KEY (waste_type_id) REFERENCES waste_types (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 점검 처리 상태와 담당 이력을 별도로 남겨 감사 추적 및 처리시간 통계에 사용한다.
CREATE TABLE IF NOT EXISTS inspection_actions (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    inspection_id   BIGINT UNSIGNED NOT NULL,
    assignee_id     BIGINT UNSIGNED NULL,
    created_by      BIGINT UNSIGNED NOT NULL,
    action_type     ENUM('REVIEW', 'COLLECTION_REQUEST', 'COLLECTION', 'REINSPECTION', 'OTHER') NOT NULL,
    status          ENUM('OPEN', 'IN_PROGRESS', 'DONE', 'CANCELLED') NOT NULL DEFAULT 'OPEN',
    description     TEXT NOT NULL,
    due_at          DATETIME(6) NULL,
    completed_at    DATETIME(6) NULL,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_inspection_actions_inspection (inspection_id, created_at DESC),
    KEY ix_inspection_actions_assignee_status (assignee_id, status, due_at),
    CONSTRAINT fk_inspection_actions_inspection FOREIGN KEY (inspection_id) REFERENCES inspections (id) ON DELETE CASCADE,
    CONSTRAINT fk_inspection_actions_assignee FOREIGN KEY (assignee_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_inspection_actions_created_by FOREIGN KEY (created_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS inspection_status_history (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    inspection_id   BIGINT UNSIGNED NOT NULL,
    changed_by      BIGINT UNSIGNED NULL COMMENT '시스템 변경이면 NULL',
    from_status     ENUM('DRAFT', 'ANALYZING', 'REVIEW_REQUIRED', 'ACTION_REQUIRED', 'RESOLVED', 'FAILED') NULL,
    to_status       ENUM('DRAFT', 'ANALYZING', 'REVIEW_REQUIRED', 'ACTION_REQUIRED', 'RESOLVED', 'FAILED') NOT NULL,
    reason          VARCHAR(1000) NULL,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_inspection_status_history_lookup (inspection_id, created_at DESC),
    CONSTRAINT fk_inspection_status_history_inspection FOREIGN KEY (inspection_id) REFERENCES inspections (id) ON DELETE CASCADE,
    CONSTRAINT fk_inspection_status_history_changed_by FOREIGN KEY (changed_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 게시판
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS board_categories (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code            VARCHAR(50) NOT NULL,
    name            VARCHAR(50) NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_board_categories_code (code),
    UNIQUE KEY uq_board_categories_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS boards (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    category_id     BIGINT UNSIGNED NOT NULL,
    author_id       BIGINT UNSIGNED NOT NULL,
    inspection_id   BIGINT UNSIGNED NULL COMMENT '점검 결과 게시글일 때 원본 점검 연결',
    title           VARCHAR(100) NOT NULL,
    summary         VARCHAR(500) NULL,
    content         MEDIUMTEXT NOT NULL COMMENT 'Markdown 원문',
    thumbnail_url   VARCHAR(1024) NULL,
    is_notice       BOOLEAN NOT NULL DEFAULT FALSE,
    status          ENUM('DRAFT', 'PUBLISHED', 'HIDDEN') NOT NULL DEFAULT 'PUBLISHED',
    view_count      BIGINT UNSIGNED NOT NULL DEFAULT 0,
    published_at    DATETIME(6) NULL,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    deleted_at      DATETIME(6) NULL,
    PRIMARY KEY (id),
    KEY ix_boards_list (status, is_notice DESC, published_at DESC, id DESC),
    KEY ix_boards_category_list (category_id, status, published_at DESC),
    KEY ix_boards_author (author_id, created_at DESC),
    FULLTEXT KEY ft_boards_search (title, summary, content),
    CONSTRAINT ck_boards_view_count CHECK (view_count >= 0),
    CONSTRAINT fk_boards_category FOREIGN KEY (category_id) REFERENCES board_categories (id),
    CONSTRAINT fk_boards_author FOREIGN KEY (author_id) REFERENCES users (id),
    CONSTRAINT fk_boards_inspection FOREIGN KEY (inspection_id) REFERENCES inspections (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS tags (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name            VARCHAR(20) NOT NULL,
    normalized_name VARCHAR(20) NOT NULL COMMENT 'trim 후 소문자 변환한 중복 판정 값',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_tags_normalized_name (normalized_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS board_tags (
    board_id        BIGINT UNSIGNED NOT NULL,
    tag_id          BIGINT UNSIGNED NOT NULL,
    sort_order      TINYINT UNSIGNED NOT NULL DEFAULT 0,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (board_id, tag_id),
    UNIQUE KEY uq_board_tags_order (board_id, sort_order),
    KEY ix_board_tags_tag (tag_id, board_id),
    CONSTRAINT ck_board_tags_sort_order CHECK (sort_order < 8),
    CONSTRAINT fk_board_tags_board FOREIGN KEY (board_id) REFERENCES boards (id) ON DELETE CASCADE,
    CONSTRAINT fk_board_tags_tag FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 기준 데이터 (여러 번 실행해도 안전)
-- ---------------------------------------------------------------------------

INSERT INTO roles (code, name, description) VALUES
    ('ADMIN', '관리자', '사용자 및 서비스 전체 관리'),
    ('MANAGER', '현장 관리자', '점검 검토와 후속 조치 관리'),
    ('INSPECTOR', '현장 점검자', '점검 생성과 결과 기록'),
    ('USER', '일반 사용자', '게시판 조회 및 허용된 글 작성')
ON DUPLICATE KEY UPDATE name = VALUES(name), description = VALUES(description);

INSERT INTO board_categories (code, name, sort_order) VALUES
    ('DEV_LOG', '개발 기록', 10),
    ('INSPECTION_RESULT', '점검 결과', 20),
    ('PROJECT_NOTICE', '프로젝트 공지', 30),
    ('COLLECTION_REQUEST', '수거 요청', 40)
ON DUPLICATE KEY UPDATE name = VALUES(name), sort_order = VALUES(sort_order);

INSERT INTO waste_types (code, name_ko, name_en) VALUES
    ('PET_BOTTLE', '페트병', 'PET Bottle'),
    ('ROPE', '로프', 'Rope'),
    ('PLASTIC_BUOY', '플라스틱 부표', 'Plastic Buoy'),
    ('STYROFOAM', '스티로폼', 'Styrofoam'),
    ('FISHING_NET', '어망', 'Fishing Net'),
    ('OTHER', '기타 폐기물', 'Other Waste')
ON DUPLICATE KEY UPDATE name_ko = VALUES(name_ko), name_en = VALUES(name_en);

-- 구현 시 트랜잭션 경계
-- * 점검 저장: inspections + inspection_images를 한 트랜잭션으로 저장한다.
-- * 분석 완료: detection_runs 상태 변경 + detections 일괄 저장 + inspections 상태 변경
--   + inspection_status_history 추가를 한 트랜잭션으로 처리한다.
-- * 게시글 저장: boards + tags upsert + board_tags를 한 트랜잭션으로 처리한다.
-- * 조회수: UPDATE boards SET view_count = view_count + 1 WHERE id = ? 로 원자 증가시킨다.
-- * 삭제: users/boards/inspections는 deleted_at 기반 soft delete, 종속 분석 데이터는 FK cascade를 사용한다.
