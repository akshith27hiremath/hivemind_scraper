-- Migration 06: Add indexes for REST API v1 feed endpoint performance
-- Run on production: docker cp this_file sp500_postgres:/tmp/ && docker exec sp500_postgres psql -U scraper_user -d sp500_news -f /tmp/06_api_v1_indexes.sql
-- Uses CONCURRENTLY to avoid table locks on production

-- Composite partial index for the feed cursor query
-- Covers: WHERE ready_for_kg=TRUE ORDER BY classified_at ASC, id ASC
-- Reduces scan from ~149K rows to ~53K FACTUAL articles, already sorted
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_feed_cursor
    ON articles_raw (classified_at ASC, id ASC)
    WHERE ready_for_kg = TRUE;

-- Index for cluster detail lookups by (batch_id, label)
-- Currently only has UNIQUE(cluster_batch_id, article_id) which doesn't help label lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_article_clusters_batch_label
    ON article_clusters (cluster_batch_id, cluster_label);
