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
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '역할 고유 식별자',
    code            VARCHAR(30) NOT NULL COMMENT '역할을 식별하는 고유 코드',
    name            VARCHAR(50) NOT NULL COMMENT '역할 표시 이름',
    description     VARCHAR(255) NULL COMMENT '역할의 용도와 권한 설명',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '역할 생성 일시',
    PRIMARY KEY (id),
    UNIQUE KEY uq_roles_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='사용자 역할 정보';

CREATE TABLE IF NOT EXISTS users (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '사용자 고유 식별자',
    role_id         BIGINT UNSIGNED NOT NULL COMMENT '사용자에게 부여된 역할 식별자',
    email           VARCHAR(254) NOT NULL COMMENT '로그인에 사용하는 고유 이메일 주소',
    password_hash   VARCHAR(255) NOT NULL COMMENT 'Argon2id 또는 bcrypt 비밀번호 해시',
    name            VARCHAR(100) NOT NULL COMMENT '사용자 표시 이름',
    status          ENUM('PENDING', 'ACTIVE', 'SUSPENDED', 'WITHDRAWN') NOT NULL DEFAULT 'ACTIVE' COMMENT '사용자 계정 상태',
    last_login_at   DATETIME(6) NULL COMMENT '마지막 로그인 일시',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '사용자 생성 일시',
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '사용자 정보 수정 일시',
    deleted_at      DATETIME(6) NULL COMMENT '소프트 삭제 일시',
    profile_file_id BIGINT UNSIGNED NULL COMMENT 'Current profile image file identifier',
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email),
    KEY ix_users_role_status (role_id, status),
    CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='사용자 계정 정보';

CREATE TABLE IF NOT EXISTS auth_sessions (
    id                  CHAR(36) NOT NULL COMMENT 'JWT sid claim에 넣는 세션 UUID',
    user_id             BIGINT UNSIGNED NOT NULL COMMENT '세션 소유 사용자 식별자',
    refresh_token_hash  CHAR(64) NULL COMMENT '리프레시 토큰의 SHA-256 해시',
    user_agent          VARCHAR(500) NULL COMMENT '접속 클라이언트 User-Agent',
    ip_address          VARCHAR(45) NULL COMMENT '접속 클라이언트 IPv4 또는 IPv6 주소',
    expires_at          DATETIME(6) NOT NULL COMMENT '세션 만료 일시',
    last_used_at        DATETIME(6) NULL COMMENT '세션 마지막 사용 일시',
    revoked_at          DATETIME(6) NULL COMMENT '세션 폐기 일시',
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '세션 생성 일시',
    PRIMARY KEY (id),
    UNIQUE KEY uq_auth_sessions_refresh_hash (refresh_token_hash),
    KEY ix_auth_sessions_user_active (user_id, revoked_at, expires_at),
    CONSTRAINT fk_auth_sessions_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='사용자 인증 세션 정보';

-- 현재 backend/sql/menu.sql API와의 호환을 위한 서비스 메뉴.
-- MinIO stores the binary object; this table stores searchable metadata only.
CREATE TABLE IF NOT EXISTS files (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'File identifier',
    uploaded_by     BIGINT UNSIGNED NOT NULL COMMENT 'Uploader user identifier',
    bucket_name     VARCHAR(63) NOT NULL COMMENT 'MinIO bucket name',
    object_key      VARCHAR(700) NOT NULL COMMENT 'Unique object key inside the bucket',
    original_name   VARCHAR(255) NOT NULL COMMENT 'Original client filename',
    mime_type       VARCHAR(255) NOT NULL COMMENT 'Uploaded Content-Type',
    byte_size       BIGINT UNSIGNED NOT NULL COMMENT 'Object size in bytes',
    etag            VARCHAR(64) NULL COMMENT 'MinIO object ETag',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    deleted_at      DATETIME(6) NULL COMMENT 'Soft deletion timestamp',
    PRIMARY KEY (id),
    UNIQUE KEY uq_files_bucket_object (bucket_name, object_key),
    KEY ix_files_uploader_created (uploaded_by, created_at DESC),
    KEY ix_files_active (deleted_at, id),
    CONSTRAINT ck_files_byte_size CHECK (byte_size > 0),
    CONSTRAINT fk_files_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='MinIO file metadata';

ALTER TABLE users
    ADD KEY ix_users_profile_file (profile_file_id),
    ADD CONSTRAINT fk_users_profile_file
        FOREIGN KEY (profile_file_id) REFERENCES files (id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS menu (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '메뉴 고유 식별자',
    parent_id       BIGINT UNSIGNED NULL COMMENT '상위 메뉴 식별자',
    name            VARCHAR(100) NOT NULL COMMENT '메뉴 표시 이름',
    path            VARCHAR(255) NOT NULL COMMENT '메뉴 라우트 또는 액션 경로',
    icon            VARCHAR(100) NULL COMMENT '메뉴 아이콘 이름 또는 식별자',
    menu_type       ENUM('GROUP', 'PAGE', 'ACTION') NOT NULL DEFAULT 'PAGE' COMMENT '메뉴 동작 유형',
    description     VARCHAR(500) NULL COMMENT '메뉴 설명',
    is_use          BOOLEAN NOT NULL DEFAULT TRUE COMMENT '메뉴 사용 여부',
    sort_order      INT NOT NULL DEFAULT 0 COMMENT '동일 계층 내 표시 순서',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '메뉴 생성 일시',
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '메뉴 수정 일시',
    PRIMARY KEY (id),
    UNIQUE KEY uq_menu_path (path),
    KEY ix_menu_active_order (is_use, sort_order),
    KEY ix_menu_parent_order (parent_id, sort_order),
    CONSTRAINT fk_menu_parent FOREIGN KEY (parent_id) REFERENCES menu (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='서비스 메뉴 구성 정보';

-- ---------------------------------------------------------------------------
-- 점검 위치와 현장 점검
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS locations (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '점검 장소 고유 식별자',
    name            VARCHAR(150) NOT NULL COMMENT '점검 장소 이름',
    address         VARCHAR(500) NULL COMMENT '점검 장소 주소',
    latitude        DECIMAL(10, 7) NULL COMMENT '점검 장소 위도',
    longitude       DECIMAL(10, 7) NULL COMMENT '점검 장소 경도',
    description     VARCHAR(1000) NULL COMMENT '점검 장소 상세 설명',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE COMMENT '점검 장소 활성 여부',
    created_by      BIGINT UNSIGNED NOT NULL COMMENT '점검 장소를 등록한 사용자 식별자',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '점검 장소 생성 일시',
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '점검 장소 수정 일시',
    PRIMARY KEY (id),
    KEY ix_locations_name (name),
    KEY ix_locations_coordinates (latitude, longitude),
    CONSTRAINT ck_locations_latitude CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CONSTRAINT ck_locations_longitude CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    CONSTRAINT fk_locations_created_by FOREIGN KEY (created_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='현장 점검 장소 정보';

CREATE TABLE IF NOT EXISTS inspections (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '점검 고유 식별자',
    location_id         BIGINT UNSIGNED NULL COMMENT '점검 장소 식별자',
    inspector_id        BIGINT UNSIGNED NOT NULL COMMENT '점검 수행 사용자 식별자',
    reviewer_id         BIGINT UNSIGNED NULL COMMENT '점검 검토 사용자 식별자',
    title               VARCHAR(200) NOT NULL COMMENT '점검 제목',
    notes               TEXT NULL COMMENT '점검자가 작성한 현장 메모',
    ai_opinion          TEXT NULL COMMENT 'LLM이 생성한 점검 의견',
    status              ENUM('DRAFT', 'ANALYZING', 'REVIEW_REQUIRED', 'ACTION_REQUIRED', 'RESOLVED', 'FAILED') NOT NULL DEFAULT 'DRAFT' COMMENT '점검 처리 상태',
    priority            ENUM('LOW', 'MEDIUM', 'HIGH', 'URGENT') NOT NULL DEFAULT 'MEDIUM' COMMENT '점검 우선순위',
    captured_at         DATETIME(6) NOT NULL COMMENT '현장 이미지 촬영 또는 점검 수행 일시',
    reviewed_at         DATETIME(6) NULL COMMENT '점검 검토 완료 일시',
    resolved_at         DATETIME(6) NULL COMMENT '점검 조치 완료 일시',
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '점검 생성 일시',
    updated_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '점검 수정 일시',
    deleted_at          DATETIME(6) NULL COMMENT '소프트 삭제 일시',
    PRIMARY KEY (id),
    KEY ix_inspections_history (captured_at DESC, id DESC),
    KEY ix_inspections_status_date (status, captured_at DESC),
    KEY ix_inspections_location_date (location_id, captured_at DESC),
    KEY ix_inspections_inspector_date (inspector_id, captured_at DESC),
    CONSTRAINT fk_inspections_location FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE SET NULL,
    CONSTRAINT fk_inspections_inspector FOREIGN KEY (inspector_id) REFERENCES users (id),
    CONSTRAINT fk_inspections_reviewer FOREIGN KEY (reviewer_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='현장 점검 및 처리 상태 정보';

CREATE TABLE IF NOT EXISTS inspection_images (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '점검 이미지 고유 식별자',
    inspection_id   BIGINT UNSIGNED NOT NULL COMMENT '이미지가 속한 점검 식별자',
    kind            ENUM('ORIGINAL', 'ANNOTATED') NOT NULL DEFAULT 'ORIGINAL' COMMENT '원본 또는 탐지 결과 표시 이미지 구분',
    storage_key     VARCHAR(1024) NOT NULL COMMENT '객체 스토리지 내부 키',
    original_name   VARCHAR(255) NULL COMMENT '업로드 당시 원본 파일 이름',
    mime_type       VARCHAR(100) NOT NULL COMMENT '이미지 MIME 유형',
    byte_size       BIGINT UNSIGNED NOT NULL COMMENT '이미지 파일 크기(바이트)',
    width           INT UNSIGNED NULL COMMENT '이미지 너비(픽셀)',
    height          INT UNSIGNED NULL COMMENT '이미지 높이(픽셀)',
    sha256          CHAR(64) NULL COMMENT '이미지 파일 SHA-256 해시',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '이미지 메타데이터 생성 일시',
    PRIMARY KEY (id),
    UNIQUE KEY uq_inspection_images_storage_key (storage_key),
    KEY ix_inspection_images_inspection_kind (inspection_id, kind),
    CONSTRAINT ck_inspection_images_byte_size CHECK (byte_size > 0),
    CONSTRAINT ck_inspection_images_dimensions CHECK ((width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)),
    CONSTRAINT fk_inspection_images_inspection FOREIGN KEY (inspection_id) REFERENCES inspections (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='점검 원본 및 분석 이미지 정보';

-- ---------------------------------------------------------------------------
-- AI 분석과 객체 탐지
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS waste_types (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '폐기물 유형 고유 식별자',
    code            VARCHAR(50) NOT NULL COMMENT 'AI 모델에서 사용하는 클래스 코드',
    name_ko         VARCHAR(100) NOT NULL COMMENT '폐기물 유형 한글 이름',
    name_en         VARCHAR(100) NULL COMMENT '폐기물 유형 영문 이름',
    description     VARCHAR(500) NULL COMMENT '폐기물 유형 상세 설명',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE COMMENT '폐기물 유형 사용 여부',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '폐기물 유형 생성 일시',
    PRIMARY KEY (id),
    UNIQUE KEY uq_waste_types_code (code),
    UNIQUE KEY uq_waste_types_name_ko (name_ko)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI가 분류하는 폐기물 유형 정보';

CREATE TABLE IF NOT EXISTS detection_runs (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'AI 탐지 실행 고유 식별자',
    inspection_id       BIGINT UNSIGNED NOT NULL COMMENT '분석 대상 점검 식별자',
    source_image_id     BIGINT UNSIGNED NOT NULL COMMENT '분석에 사용한 원본 이미지 식별자',
    annotated_image_id  BIGINT UNSIGNED NULL COMMENT '탐지 결과가 표시된 이미지 식별자',
    model_name          VARCHAR(100) NOT NULL COMMENT '추론에 사용한 AI 모델 이름',
    model_version       VARCHAR(100) NOT NULL COMMENT '추론에 사용한 AI 모델 버전',
    status              ENUM('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED') NOT NULL DEFAULT 'QUEUED' COMMENT 'AI 탐지 실행 상태',
    inference_ms        INT UNSIGNED NULL COMMENT 'AI 모델 추론 소요 시간(밀리초)',
    raw_result          JSON NULL COMMENT 'AI 모델의 정규화 전 원본 응답',
    error_message       TEXT NULL COMMENT '탐지 실패 시 오류 메시지',
    started_at          DATETIME(6) NULL COMMENT '탐지 실행 시작 일시',
    completed_at        DATETIME(6) NULL COMMENT '탐지 실행 완료 일시',
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '탐지 실행 레코드 생성 일시',
    PRIMARY KEY (id),
    KEY ix_detection_runs_inspection (inspection_id, created_at DESC),
    KEY ix_detection_runs_status_created (status, created_at),
    CONSTRAINT ck_detection_runs_time CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at),
    CONSTRAINT fk_detection_runs_inspection FOREIGN KEY (inspection_id) REFERENCES inspections (id) ON DELETE CASCADE,
    CONSTRAINT fk_detection_runs_source_image FOREIGN KEY (source_image_id) REFERENCES inspection_images (id),
    CONSTRAINT fk_detection_runs_annotated_image FOREIGN KEY (annotated_image_id) REFERENCES inspection_images (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 객체 탐지 실행 정보';

CREATE TABLE IF NOT EXISTS detections (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '탐지 객체 고유 식별자',
    detection_run_id BIGINT UNSIGNED NOT NULL COMMENT '탐지 객체가 속한 AI 실행 식별자',
    waste_type_id   BIGINT UNSIGNED NOT NULL COMMENT '탐지된 폐기물 유형 식별자',
    confidence      DECIMAL(6, 5) NOT NULL COMMENT '0부터 1 사이의 탐지 신뢰도',
    bbox_x          DECIMAL(8, 7) NOT NULL COMMENT '0부터 1로 정규화된 바운딩 박스 좌상단 X 좌표',
    bbox_y          DECIMAL(8, 7) NOT NULL COMMENT '0부터 1로 정규화된 바운딩 박스 좌상단 Y 좌표',
    bbox_width      DECIMAL(8, 7) NOT NULL COMMENT '0부터 1로 정규화된 바운딩 박스 너비',
    bbox_height     DECIMAL(8, 7) NOT NULL COMMENT '0부터 1로 정규화된 바운딩 박스 높이',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '탐지 객체 생성 일시',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 실행에서 탐지된 개별 객체 정보';

-- 점검 처리 상태와 담당 이력을 별도로 남겨 감사 추적 및 처리시간 통계에 사용한다.
CREATE TABLE IF NOT EXISTS inspection_actions (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '점검 후속 조치 고유 식별자',
    inspection_id   BIGINT UNSIGNED NOT NULL COMMENT '후속 조치 대상 점검 식별자',
    assignee_id     BIGINT UNSIGNED NULL COMMENT '후속 조치 담당 사용자 식별자',
    created_by      BIGINT UNSIGNED NOT NULL COMMENT '후속 조치를 등록한 사용자 식별자',
    action_type     ENUM('REVIEW', 'COLLECTION_REQUEST', 'COLLECTION', 'REINSPECTION', 'OTHER') NOT NULL COMMENT '후속 조치 유형',
    status          ENUM('OPEN', 'IN_PROGRESS', 'DONE', 'CANCELLED') NOT NULL DEFAULT 'OPEN' COMMENT '후속 조치 진행 상태',
    description     TEXT NOT NULL COMMENT '후속 조치 상세 내용',
    due_at          DATETIME(6) NULL COMMENT '후속 조치 완료 기한',
    completed_at    DATETIME(6) NULL COMMENT '후속 조치 완료 일시',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '후속 조치 생성 일시',
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '후속 조치 수정 일시',
    PRIMARY KEY (id),
    KEY ix_inspection_actions_inspection (inspection_id, created_at DESC),
    KEY ix_inspection_actions_assignee_status (assignee_id, status, due_at),
    CONSTRAINT fk_inspection_actions_inspection FOREIGN KEY (inspection_id) REFERENCES inspections (id) ON DELETE CASCADE,
    CONSTRAINT fk_inspection_actions_assignee FOREIGN KEY (assignee_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_inspection_actions_created_by FOREIGN KEY (created_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='점검 후속 조치 및 처리 이력';

CREATE TABLE IF NOT EXISTS inspection_status_history (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '점검 상태 변경 이력 고유 식별자',
    inspection_id   BIGINT UNSIGNED NOT NULL COMMENT '상태가 변경된 점검 식별자',
    changed_by      BIGINT UNSIGNED NULL COMMENT '상태를 변경한 사용자 식별자이며 시스템 변경이면 NULL',
    from_status     ENUM('DRAFT', 'ANALYZING', 'REVIEW_REQUIRED', 'ACTION_REQUIRED', 'RESOLVED', 'FAILED') NULL COMMENT '변경 전 점검 상태',
    to_status       ENUM('DRAFT', 'ANALYZING', 'REVIEW_REQUIRED', 'ACTION_REQUIRED', 'RESOLVED', 'FAILED') NOT NULL COMMENT '변경 후 점검 상태',
    reason          VARCHAR(1000) NULL COMMENT '상태 변경 사유',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '상태 변경 일시',
    PRIMARY KEY (id),
    KEY ix_inspection_status_history_lookup (inspection_id, created_at DESC),
    CONSTRAINT fk_inspection_status_history_inspection FOREIGN KEY (inspection_id) REFERENCES inspections (id) ON DELETE CASCADE,
    CONSTRAINT fk_inspection_status_history_changed_by FOREIGN KEY (changed_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='점검 상태 변경 이력';

-- ---------------------------------------------------------------------------
-- 게시판
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS board_categories (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '게시판 카테고리 고유 식별자',
    code            VARCHAR(50) NOT NULL COMMENT '게시판 카테고리를 식별하는 고유 코드',
    name            VARCHAR(50) NOT NULL COMMENT '게시판 카테고리 표시 이름',
    sort_order      INT NOT NULL DEFAULT 0 COMMENT '게시판 카테고리 표시 순서',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE COMMENT '게시판 카테고리 사용 여부',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '게시판 카테고리 생성 일시',
    PRIMARY KEY (id),
    UNIQUE KEY uq_board_categories_code (code),
    UNIQUE KEY uq_board_categories_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='게시판 카테고리 정보';

CREATE TABLE IF NOT EXISTS boards (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '게시글 고유 식별자',
    category_id     BIGINT UNSIGNED NOT NULL COMMENT '게시글 카테고리 식별자',
    author_id       BIGINT UNSIGNED NOT NULL COMMENT '게시글 작성자 식별자',
    inspection_id   BIGINT UNSIGNED NULL COMMENT '게시글에 연결된 원본 점검 식별자',
    title           VARCHAR(100) NOT NULL COMMENT '게시글 제목',
    summary         VARCHAR(500) NULL COMMENT '게시글 요약',
    content         MEDIUMTEXT NOT NULL COMMENT 'Markdown 형식의 게시글 본문',
    thumbnail_url   VARCHAR(1024) NULL COMMENT '게시글 썸네일 이미지 URL',
    is_notice       BOOLEAN NOT NULL DEFAULT FALSE COMMENT '공지 게시글 여부',
    status          ENUM('DRAFT', 'PUBLISHED', 'HIDDEN') NOT NULL DEFAULT 'PUBLISHED' COMMENT '게시글 공개 상태',
    view_count      BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '게시글 조회 수',
    published_at    DATETIME(6) NULL COMMENT '게시글 공개 일시',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '게시글 생성 일시',
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '게시글 수정 일시',
    deleted_at      DATETIME(6) NULL COMMENT '소프트 삭제 일시',
    PRIMARY KEY (id),
    KEY ix_boards_list (status, is_notice DESC, published_at DESC, id DESC),
    KEY ix_boards_category_list (category_id, status, published_at DESC),
    KEY ix_boards_author (author_id, created_at DESC),
    FULLTEXT KEY ft_boards_search (title, summary, content),
    CONSTRAINT ck_boards_view_count CHECK (view_count >= 0),
    CONSTRAINT fk_boards_category FOREIGN KEY (category_id) REFERENCES board_categories (id),
    CONSTRAINT fk_boards_author FOREIGN KEY (author_id) REFERENCES users (id),
    CONSTRAINT fk_boards_inspection FOREIGN KEY (inspection_id) REFERENCES inspections (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='게시판 게시글 정보';

CREATE TABLE IF NOT EXISTS tags (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '태그 고유 식별자',
    name            VARCHAR(20) NOT NULL COMMENT '사용자에게 표시되는 태그 이름',
    normalized_name VARCHAR(20) NOT NULL COMMENT '공백 제거 및 소문자 변환을 거친 중복 판정 값',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '태그 생성 일시',
    PRIMARY KEY (id),
    UNIQUE KEY uq_tags_normalized_name (normalized_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='게시글 분류용 태그 정보';

CREATE TABLE IF NOT EXISTS board_tags (
    board_id        BIGINT UNSIGNED NOT NULL COMMENT '태그가 연결된 게시글 식별자',
    tag_id          BIGINT UNSIGNED NOT NULL COMMENT '게시글에 연결된 태그 식별자',
    sort_order      TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '게시글 내 태그 표시 순서',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '게시글과 태그 연결 생성 일시',
    PRIMARY KEY (board_id, tag_id),
    UNIQUE KEY uq_board_tags_order (board_id, sort_order),
    KEY ix_board_tags_tag (tag_id, board_id),
    CONSTRAINT ck_board_tags_sort_order CHECK (sort_order < 8),
    CONSTRAINT fk_board_tags_board FOREIGN KEY (board_id) REFERENCES boards (id) ON DELETE CASCADE,
    CONSTRAINT fk_board_tags_tag FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='게시글과 태그의 연결 정보';

CREATE TABLE IF NOT EXISTS board_comments (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '댓글 고유 식별자',
    board_id            BIGINT UNSIGNED NOT NULL COMMENT '댓글이 작성된 게시글 식별자',
    author_id           BIGINT UNSIGNED NOT NULL COMMENT '댓글 작성자 식별자',
    parent_comment_id   BIGINT UNSIGNED NULL COMMENT '대댓글이 답변하는 부모 댓글 식별자; NULL이면 최상위 댓글',
    content             TEXT NOT NULL COMMENT '댓글 본문',
    emoticon            VARCHAR(40) NULL COMMENT '이모티콘 파일 식별자',
    status              ENUM('ACTIVE', 'HIDDEN', 'DELETED') NOT NULL DEFAULT 'ACTIVE' COMMENT '댓글 운영 상태',
    moderated_by        BIGINT UNSIGNED NULL COMMENT '마지막 조치 관리자 식별자',
    moderated_at        DATETIME(6) NULL COMMENT '마지막 관리자 조치 일시',
    moderation_reason   VARCHAR(500) NULL COMMENT '마지막 관리자 조치 사유',
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '댓글 생성 일시',
    updated_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '댓글 수정 일시',
    deleted_at          DATETIME(6) NULL COMMENT '소프트 삭제 일시',
    PRIMARY KEY (id),
    UNIQUE KEY uq_board_comments_board_id (board_id, id),
    KEY ix_board_comments_thread (board_id, parent_comment_id, deleted_at, created_at, id),
    KEY ix_board_comments_author (author_id, deleted_at, created_at DESC),
    KEY ix_board_comments_moderation (status, created_at DESC),
    CONSTRAINT ck_board_comments_body CHECK (CHAR_LENGTH(TRIM(content)) > 0 OR emoticon IS NOT NULL),
    CONSTRAINT fk_board_comments_board FOREIGN KEY (board_id) REFERENCES boards (id) ON DELETE CASCADE,
    CONSTRAINT fk_board_comments_author FOREIGN KEY (author_id) REFERENCES users (id),
    CONSTRAINT fk_board_comments_moderated_by FOREIGN KEY (moderated_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_board_comments_parent FOREIGN KEY (board_id, parent_comment_id)
        REFERENCES board_comments (board_id, id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='게시글 댓글 및 대댓글 정보';

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

CREATE TABLE IF NOT EXISTS forbidden_words (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '금칙어 식별자',
    word            VARCHAR(100) NOT NULL COMMENT '표시용 금칙어',
    normalized_word VARCHAR(100) NOT NULL COMMENT '소문자 및 공백 제거된 중복 판정 값',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE COMMENT '탐지 사용 여부',
    created_by      BIGINT UNSIGNED NULL COMMENT '등록 관리자',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_forbidden_words_normalized (normalized_word),
    KEY ix_forbidden_words_active (is_active, id),
    CONSTRAINT fk_forbidden_words_created_by FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='관리자 설정 금칙어';

CREATE TABLE IF NOT EXISTS content_moderation_flags (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '탐지 결과 식별자',
    forbidden_word_id BIGINT UNSIGNED NOT NULL COMMENT '탐지된 금칙어',
    content_type    ENUM('BOARD', 'COMMENT') NOT NULL COMMENT '콘텐츠 유형',
    content_id      BIGINT UNSIGNED NOT NULL COMMENT '게시글 또는 댓글 식별자',
    matched_text    VARCHAR(100) NOT NULL COMMENT '탐지된 문자열',
    excerpt         VARCHAR(500) NOT NULL COMMENT '관리자 검토용 주변 문맥',
    status          ENUM('OPEN', 'RESOLVED', 'DISMISSED') NOT NULL DEFAULT 'OPEN' COMMENT '검토 상태',
    resolved_by     BIGINT UNSIGNED NULL COMMENT '처리 관리자',
    resolved_at     DATETIME(6) NULL COMMENT '처리 일시',
    resolution_note VARCHAR(500) NULL COMMENT '처리 메모',
    detected_at     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_content_moderation_flag (forbidden_word_id, content_type, content_id),
    KEY ix_content_moderation_flags_status (status, detected_at DESC),
    KEY ix_content_moderation_flags_content (content_type, content_id),
    CONSTRAINT fk_content_flags_word FOREIGN KEY (forbidden_word_id) REFERENCES forbidden_words (id) ON DELETE CASCADE,
    CONSTRAINT fk_content_flags_resolved_by FOREIGN KEY (resolved_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='게시글·댓글 금칙어 탐지 결과';

-- ---------------------------------------------------------------------------
-- 운영 감사 및 사용자 활동 모니터링
-- ---------------------------------------------------------------------------

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
