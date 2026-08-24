-- Existing databases only: add candidate selection state without recreating ai_models.
ALTER TABLE ai_models
    ADD COLUMN is_candidate BOOLEAN NOT NULL DEFAULT FALSE AFTER is_selected;