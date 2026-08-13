-- Phase 1 detection review fields. Apply once to an existing database.
ALTER TABLE detections
    ADD COLUMN review_result ENUM('UNREVIEWED','TRUE_POSITIVE','FALSE_POSITIVE','FALSE_NEGATIVE') NOT NULL DEFAULT 'UNREVIEWED' AFTER bbox_height,
    ADD COLUMN review_status ENUM('UNLABELED','LABELED','REVIEW_REQUIRED','REVIEWED','APPROVED','REJECTED') NOT NULL DEFAULT 'REVIEW_REQUIRED' AFTER review_result,
    ADD COLUMN actual_waste_type_id BIGINT UNSIGNED NULL AFTER review_status,
    ADD COLUMN error_reason VARCHAR(500) NULL AFTER actual_waste_type_id,
    ADD COLUMN retraining_candidate BOOLEAN NOT NULL DEFAULT FALSE AFTER error_reason,
    ADD COLUMN reviewed_by BIGINT UNSIGNED NULL AFTER retraining_candidate,
    ADD COLUMN reviewed_at DATETIME(6) NULL AFTER reviewed_by,
    ADD KEY ix_detections_review (review_result, review_status, retraining_candidate),
    ADD CONSTRAINT fk_detections_actual_type FOREIGN KEY (actual_waste_type_id) REFERENCES waste_types(id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_detections_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL;
