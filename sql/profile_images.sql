-- Apply after sql/files.sql on an existing database.
ALTER TABLE users
    ADD COLUMN profile_file_id BIGINT UNSIGNED NULL COMMENT 'Current profile image file identifier',
    ADD KEY ix_users_profile_file (profile_file_id),
    ADD CONSTRAINT fk_users_profile_file
        FOREIGN KEY (profile_file_id) REFERENCES files (id) ON DELETE SET NULL;

