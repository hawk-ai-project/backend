-- Phase 2: data browser, categorized tags and bulk workflow.
CREATE TABLE IF NOT EXISTS data_tag_categories (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500) NULL,
    created_by BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id), UNIQUE KEY uq_data_tag_categories_code (code),
    CONSTRAINT fk_data_tag_category_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS data_tags (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    category_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(100) NOT NULL,
    normalized_name VARCHAR(100) NOT NULL,
    description VARCHAR(500) NULL,
    created_by BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id), UNIQUE KEY uq_data_tags_name (normalized_name),
    KEY ix_data_tags_category (category_id, name),
    CONSTRAINT fk_data_tags_category FOREIGN KEY (category_id) REFERENCES data_tag_categories(id),
    CONSTRAINT fk_data_tags_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS inspection_data_tags (
    inspection_id BIGINT UNSIGNED NOT NULL,
    tag_id BIGINT UNSIGNED NOT NULL,
    created_by BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (inspection_id, tag_id), KEY ix_inspection_data_tags_tag (tag_id, inspection_id),
    CONSTRAINT fk_inspection_data_tags_inspection FOREIGN KEY (inspection_id) REFERENCES inspections(id) ON DELETE CASCADE,
    CONSTRAINT fk_inspection_data_tags_tag FOREIGN KEY (tag_id) REFERENCES data_tags(id) ON DELETE CASCADE,
    CONSTRAINT fk_inspection_data_tags_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO data_tag_categories (code,name,description) VALUES
('ENVIRONMENT','환경','시간, 날씨, 해상 및 조명 조건'),
('OBJECT','객체','크기, 침수, 상태 및 거리'),
('AI_ERROR','AI 오류','오탐과 미탐의 원인'),
('DATA','데이터','재학습, 우선순위 및 Hard Example')
ON DUPLICATE KEY UPDATE name=VALUES(name),description=VALUES(description);

INSERT INTO data_tags (category_id,name,normalized_name,description)
SELECT c.id,v.name,v.name,NULL FROM data_tag_categories c JOIN (
 SELECT 'ENVIRONMENT' code,'daytime' name UNION ALL SELECT 'ENVIRONMENT','night'
 UNION ALL SELECT 'ENVIRONMENT','strong-reflection' UNION ALL SELECT 'ENVIRONMENT','wave-high'
 UNION ALL SELECT 'OBJECT','small-object' UNION ALL SELECT 'OBJECT','partially-submerged'
 UNION ALL SELECT 'OBJECT','occluded' UNION ALL SELECT 'AI_ERROR','false-positive'
 UNION ALL SELECT 'AI_ERROR','false-negative' UNION ALL SELECT 'AI_ERROR','class-mismatch'
 UNION ALL SELECT 'DATA','hard-example' UNION ALL SELECT 'DATA','retraining'
) v ON v.code=c.code ON DUPLICATE KEY UPDATE name=VALUES(name);
