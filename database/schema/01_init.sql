-- S&P 500 News Aggregation System
-- Database Schema - Phase 1

-- Companies table: S&P 500 constituents
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(100),
    industry VARCHAR(100),
    cik VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_companies_ticker ON companies(ticker);
CREATE INDEX idx_companies_sector ON companies(sector);

-- Raw articles table: All fetched news articles
CREATE TABLE IF NOT EXISTS articles_raw (
    id SERIAL PRIMARY KEY,
    url VARCHAR(1000) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    source VARCHAR(100) NOT NULL,
    published_at TIMESTAMP,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_articles_url ON articles_raw(url);
CREATE INDEX idx_articles_source ON articles_raw(source);
CREATE INDEX idx_articles_published ON articles_raw(published_at DESC);
CREATE INDEX idx_articles_fetched ON articles_raw(fetched_at DESC);

-- Create a function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';
