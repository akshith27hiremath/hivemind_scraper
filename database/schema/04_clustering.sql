-- Migration: Add clustering tables and columns
-- Matches production schema on droplet (verified 2026-02-11)

-- Clustering columns on articles_raw
ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS
    cluster_batch_id UUID;

ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS
    cluster_label INTEGER;

ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS
    is_cluster_centroid BOOLEAN;

ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS
    distance_to_centroid DOUBLE PRECISION;

-- Index for cluster batch lookups
CREATE INDEX IF NOT EXISTS idx_articles_cluster_batch
    ON articles_raw(cluster_batch_id);

-- Audit table: one row per article per clustering batch
CREATE TABLE IF NOT EXISTS article_clusters (
    id SERIAL PRIMARY KEY,
    cluster_batch_id UUID NOT NULL,
    article_id INTEGER REFERENCES articles_raw(id),
    cluster_label INTEGER,
    is_centroid BOOLEAN,
    distance_to_centroid DOUBLE PRECISION,
    clustering_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE(cluster_batch_id, article_id)
);
