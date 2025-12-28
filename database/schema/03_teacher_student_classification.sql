-- Migration: Add teacher-student classification columns
-- Run this migration to add classification support

-- Classification columns on articles_raw
ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS
    classification_label VARCHAR(20);  -- 'FACTUAL', 'OPINION', 'SLOP'

ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS
    classification_confidence DOUBLE PRECISION;  -- 0.0-1.0

ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS
    classification_source VARCHAR(20);  -- 'teacher' or 'student'

ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS
    classification_model_version VARCHAR(50);  -- e.g., 'student-v1.0', 'gpt-4o-2024'

ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS
    classified_at TIMESTAMP;

ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS
    ready_for_kg BOOLEAN DEFAULT FALSE;  -- Mark FACTUAL articles for KG ingestion

-- Index for filtering by classification
CREATE INDEX IF NOT EXISTS idx_articles_classification
    ON articles_raw(classification_label)
    WHERE classification_label IS NOT NULL;

-- Index for knowledge graph ingestion
CREATE INDEX IF NOT EXISTS idx_articles_ready_kg
    ON articles_raw(ready_for_kg)
    WHERE ready_for_kg = TRUE;

-- Teacher labels table (for retraining)
CREATE TABLE IF NOT EXISTS teacher_labels (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles_raw(id) ON DELETE CASCADE,
    label VARCHAR(20) NOT NULL,  -- 'FACTUAL', 'OPINION', 'SLOP'
    confidence DOUBLE PRECISION,
    reasoning TEXT,
    teacher_model VARCHAR(100) NOT NULL,  -- 'gpt-4o-2024-08-06'
    prompt_version VARCHAR(50) DEFAULT 'v1',
    labeled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article_id, teacher_model, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_teacher_labels_article
    ON teacher_labels(article_id);

CREATE INDEX IF NOT EXISTS idx_teacher_labels_model
    ON teacher_labels(teacher_model);
