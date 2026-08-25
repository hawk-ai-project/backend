CREATE TABLE IF NOT EXISTS ai_model_recommendation_cache (
  context_type VARCHAR(32) NOT NULL,
  inspection_id BIGINT NOT NULL DEFAULT 0,
  response_json JSON NOT NULL,
  generated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (context_type, inspection_id)
);
