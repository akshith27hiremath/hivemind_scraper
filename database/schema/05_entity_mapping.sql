-- Migration: Add article-company entity mapping junction table
-- Links articles to S&P 500 companies mentioned in title/summary

CREATE TABLE IF NOT EXISTS article_company_mentions (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles_raw(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    mention_type VARCHAR(10) NOT NULL,      -- 'title', 'summary', 'both'
    match_method VARCHAR(10) NOT NULL,      -- 'ticker', 'name', 'alias', 'brand'
    matched_text TEXT,
    confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article_id, company_id)
);

CREATE INDEX IF NOT EXISTS idx_acm_company_id ON article_company_mentions(company_id);
CREATE INDEX IF NOT EXISTS idx_acm_ticker ON article_company_mentions(ticker);
CREATE INDEX IF NOT EXISTS idx_acm_article_id ON article_company_mentions(article_id);

-- Track which articles have been processed by entity mapper (regardless of match)
ALTER TABLE articles_raw ADD COLUMN IF NOT EXISTS entity_mapped_at TIMESTAMP;
