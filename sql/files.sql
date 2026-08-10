-- Apply this migration to an existing Hawk-AI MySQL database.
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

