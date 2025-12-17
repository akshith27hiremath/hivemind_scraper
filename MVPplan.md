# **MVP Implementation Guide: S&P 500 News Aggregation System**
## **Lean, Focused Plan for Rapid Deployment**

---

## **TABLE OF CONTENTS**

1. [MVP Philosophy & Scope](#1-mvp-philosophy--scope)
2. [System Architecture (Simplified)](#2-system-architecture-simplified)
3. [Data Sources (MVP Only)](#3-data-sources-mvp-only)
4. [Phase 1: Basic Ingestion (Week 1-2)](#phase-1-basic-ingestion-week-1-2)
5. [Phase 2: Core Processing (Week 3-4)](#phase-2-core-processing-week-3-4)
6. [Phase 3: Simple Storage (Week 5)](#phase-3-simple-storage-week-5)
7. [Phase 4: Basic API (Week 6)](#phase-4-basic-api-week-6)
8. [Phase 5: Essential Features (Week 7-8)](#phase-5-essential-features-week-7-8)
9. [MVP Infrastructure](#mvp-infrastructure)
10. [MVP Cost Analysis](#mvp-cost-analysis)
11. [MVP Success Criteria](#mvp-success-criteria)
12. [Post-MVP Roadmap](#post-mvp-roadmap)

---

## **1. MVP PHILOSOPHY & SCOPE**

### **Core MVP Principle**
Build the **minimum viable system** to feed your Knowledge Graph with S&P 500 news in **8 weeks** with **<$100/month** budget.

### **What's IN the MVP**

**Must-Have Features:**
- ✅ News from 10-15 reliable free sources (RSS + APIs)
- ✅ Coverage of all 500 S&P 500 companies
- ✅ Basic Named Entity Recognition (company detection)
- ✅ Simple sentiment analysis (positive/negative/neutral)
- ✅ URL-based deduplication (prevent duplicate ingestion)
- ✅ Simple REST API with core endpoints
- ✅ 30 days of data retention
- ✅ Basic search and filtering

**Expected Output:**
- 1,500-2,500 unique articles per day
- 80%+ accuracy on company detection
- API response time <1 second
- Good enough to start building your Knowledge Graph layer

### **What's OUT of the MVP**

**Explicitly Excluded (Add Post-MVP):**
- ❌ Twitter/X integration
- ❌ Web scraping (too complex, legal risk)
- ❌ Advanced NLP (fine-tuned models, entity relationships)
- ❌ Complex deduplication (content similarity)
- ❌ Multiple languages (English only)
- ❌ Real-time streaming (batch processing is fine)
- ❌ Sophisticated relevance scoring (use simple heuristics)
- ❌ User authentication (single internal API key)
- ❌ Advanced analytics dashboards
- ❌ Elasticsearch (PostgreSQL full-text search sufficient)
- ❌ Kubernetes/complex orchestration
- ❌ Historical data beyond 30 days

### **MVP Success Definition**

**You succeed if:**
1. Your trading dashboard can query news for any S&P 500 company
2. You get 1,500+ articles/day with reasonable quality
3. System runs reliably with minimal maintenance
4. Total cost <$100/month
5. You can start building your Knowledge Graph on top of this data

**You can iterate on:**
- Data quality improvements
- More sophisticated NLP
- Additional sources
- Better relevance scoring
- Advanced features

---

## **2. SYSTEM ARCHITECTURE (SIMPLIFIED)**

### **Minimalist Architecture (Containerized)**

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES (Free Only)                  │
│  • 10 RSS Feeds                                             │
│  • 2-3 Free News APIs                                       │
│  • SEC EDGAR (Government)                                   │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │  DOCKER CONTAINER   │
        │  Ingestion Worker   │
        │  • APScheduler      │
        │  • RSS Parser       │
        │  • API Clients      │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │  DOCKER CONTAINER   │
        │  Processing Worker  │
        │  • Content extract  │
        │  • NER (spaCy)     │
        │  • Sentiment       │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │  DOCKER CONTAINER   │
        │  PostgreSQL         │
        │  • Articles         │
        │  • Companies        │
        │  • Entity mentions  │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │  DOCKER CONTAINER   │
        │  FastAPI REST API   │
        │  • 5 core endpoints │
        │  • Port 8000        │
        └──────────┬──────────┘
                   │
                   ▼
         ┌──────────────────────┐
         │  Your Trading        │
         │  Dashboard + KG      │
         │  (External App)      │
         └──────────────────────┘

All containers orchestrated via Docker Compose
Network: Internal bridge network + API exposed externally
```

### **Technology Stack (Keep It Simple)**

**Backend:** Python 3.11+
- Easy to write, excellent NLP libraries
- Single language for entire stack

**Database:** PostgreSQL 15+ with full-text search
- No Elasticsearch needed (KISS principle)
- pg_trgm extension for fuzzy matching

**Scheduler:** APScheduler (Python library)
- No Airflow/Prefect complexity
- Simple in-process scheduling

**API:** FastAPI
- Fast, modern, auto-generates docs
- Easy to deploy

**NLP Libraries:**
- spaCy (NER) - lightweight, fast
- VADER (sentiment) - rule-based, no ML needed for MVP
- newspaper3k (content extraction)

**Infrastructure:**
- Docker Compose for BOTH local dev AND production
- All services containerized from day 1
- Single VPS for production ($20-40/month)
- Identical setup locally and in cloud (dev/prod parity)

**Containerization Strategy:**
- Each service = separate Docker container
- Docker Compose orchestrates all containers
- Shared Docker network for inter-service communication
- Only API container exposes external port (8000)

**No Message Queue:** Direct database writes (simpler, good enough for MVP)

**No Redis:** PostgreSQL caching is sufficient initially

**No Object Storage:** Store raw HTML in database (optimize later if needed)

---

## **3. DATA SOURCES (MVP ONLY)**

### **Tier 1: Free RSS Feeds (Primary Sources)**

**Use These 10 Feeds (Reliable, High-Quality):**

| Source | URL | Update Frequency | Expected Articles/Day |
|--------|-----|------------------|----------------------|
| **Reuters Business** | `https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best` | Real-time | 50-100 |
| **MarketWatch** | `https://feeds.marketwatch.com/marketwatch/marketpulse/` | Real-time | 30-50 |
| **Yahoo Finance** | `https://finance.yahoo.com/news/rssindex` | Real-time | 100-150 |
| **Seeking Alpha** | `https://seekingalpha.com/market_currents.xml` | Real-time | 50-100 |
| **Investing.com** | `https://www.investing.com/rss/news.rss` | Real-time | 40-80 |
| **CNBC** | `https://www.cnbc.com/id/100003114/device/rss/rss.html` | Real-time | 30-60 |
| **Benzinga** | `https://www.benzinga.com/feeds/all` | Real-time | 50-100 |
| **TechCrunch** | `https://techcrunch.com/feed/` | Daily | 20-40 |
| **The Verge** | `https://www.theverge.com/rss/index.xml` | Daily | 15-30 |
| **SEC EDGAR (500 feeds)** | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&output=atom` | As filed | 5-10 total |

**Expected Total from RSS:** 400-700 raw articles/day (before dedup)

**Implementation Notes:**
- Poll every 15 minutes during market hours (9 AM - 6 PM ET)
- Poll every 1 hour outside market hours
- Use conditional GET (ETag/Last-Modified headers) to save bandwidth
- Start with these 10, don't add more until MVP is proven

### **Tier 2: Free News APIs (Supplementary)**

**Use These 2 APIs Only:**

**1. Finnhub (Free Tier)**
- **Endpoint:** `https://finnhub.io/api/v1/company-news`
- **Free Limit:** 60 calls/minute, 500 calls/day total
- **Strategy:** Query top 50 S&P 500 companies only (by market cap)
- **Frequency:** Once every 4 hours per company = 50 × 6 = 300 calls/day
- **Expected Articles:** 200-400/day
- **Why:** Excellent quality, reliable, good company-specific coverage

**2. Alpha Vantage (Free Tier)**
- **Endpoint:** `https://www.alphavantage.co/query?function=NEWS_SENTIMENT`
- **Free Limit:** 500 calls/day, 5 calls/minute
- **Strategy:** Query major events/earnings for top 100 companies
- **Frequency:** Once daily per company = 100 calls/day
- **Expected Articles:** 300-500/day (includes sentiment data)
- **Why:** Free sentiment analysis included, saves processing

**Expected Total from APIs:** 500-900 articles/day

**APIs to Skip for MVP:**
- ❌ NewsAPI.org (100/day too limited, paid tier too expensive)
- ❌ Polygon.io (requires paid subscription for sufficient volume)
- ❌ IEX Cloud (credit system too complex for MVP)

### **Tier 3: SEC EDGAR (Official, Always Free)**

**Implementation:**
- Maintain mapping: 500 tickers → CIK numbers
- Generate 500 RSS feed URLs (one per company)
- Check each feed once every 2 hours
- Expected filings: 5-10 per day across all companies

**Why Include:**
- Zero cost, unlimited usage
- High signal-to-noise ratio (every filing is material)
- Essential for earnings dates, major events
- Government source = highest reliability

### **Total Expected MVP Volume**

**Daily Article Ingestion:**
- RSS Feeds: ~600 articles/day
- APIs: ~700 articles/day
- SEC Filings: ~10 articles/day
- **Total Raw:** ~1,300 articles/day

**After URL Deduplication:** ~1,000 unique articles/day

**After Entity Filtering (S&P 500 only):** ~800-1,000 articles/day

**This is sufficient for MVP.** You'll have multiple articles per day for top 100 companies, and at least weekly coverage for long-tail companies.

---

## **PHASE 1: BASIC INGESTION (WEEK 1-2)**

### **Goal**
Fetch articles from RSS feeds and APIs, store raw data in database.

### **Week 1: RSS Aggregator + Docker Foundation**

**Tasks:**
- [ ] **Set up Docker development environment**
  - Install Docker Desktop
  - Create project structure:
    ```
    scraperMVP/
    ├── docker-compose.yml
    ├── .env.example
    ├── database/
    │   ├── Dockerfile
    │   └── init.sql
    ├── ingestion-worker/
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   └── src/
    └── README.md
    ```
- [ ] **Create initial docker-compose.yml**
  - PostgreSQL service
  - Ingestion worker service
  - Shared network
  - Volume for database persistence
- [ ] **Set up PostgreSQL container**
  - Use official postgres:15-alpine image
  - Create init.sql with database schema
  - Create `articles_raw` table
  - Columns: id, url (unique), title, summary, source, published_at, fetched_at, raw_json
- [ ] Create S&P 500 reference data file (CSV with ticker, name, sector)
  - Download from: `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies`
  - Extract: ticker, company name, sector
  - Store in database/init.sql as seed data
- [ ] **Build ingestion worker container**
  - Create Dockerfile with Python 3.11-slim base
  - Install dependencies: `feedparser`, `requests`, `python-dotenv`, `psycopg2-binary`, `APScheduler`
  - Copy source code into container
  - Set up entrypoint script
- [ ] Write RSS feed parser (in ingestion-worker/src/)
  - Parse 10 RSS feeds
  - Extract: title, link, published_date, summary, source
  - Handle encoding issues (UTF-8)
  - Connect to PostgreSQL via Docker network (hostname: postgres)
- [ ] Implement URL-based deduplication
  - Check if URL exists before inserting
  - Skip duplicates
- [ ] Write simple scheduler (APScheduler)
  - Run every 15 minutes
  - Log results to console (visible in `docker logs`)
- [ ] **Test full containerized setup**
  - `docker-compose up` starts all services
  - Ingestion worker connects to database
  - RSS feeds are fetched and stored
  - View logs: `docker-compose logs -f ingestion-worker`

**Deliverables:**
- Working Docker Compose setup with 2 containers (database + ingestion worker)
- RSS parser running inside container
- PostgreSQL database with `articles_raw` table
- Scheduler running automatically inside container
- Logs showing successful fetches (viewable via `docker logs`)

**Success Criteria:**
- `docker-compose up -d` starts all services successfully
- Fetch 400+ articles/day from RSS feeds
- No crashes or unhandled exceptions
- Duplicates prevented by URL check
- Database filling up with raw articles
- Can rebuild containers without losing data (persistent volumes)
- Services restart automatically on failure (Docker restart policy)

**Time Estimate:** 4-5 days (includes Docker setup)

---

### **Week 2: API Integration + SEC EDGAR (Containerized)**

**Tasks:**
- [ ] Register for API keys (Finnhub, Alpha Vantage)
- [ ] **Update Docker environment variables**
  - Add API keys to .env file (not committed to git)
  - Pass secrets to container via docker-compose.yml environment section
  - Example: `FINNHUB_API_KEY=${FINNHUB_API_KEY}`
- [ ] Build API clients for both services (in ingestion-worker)
  - Standardize response format
  - Handle rate limits (track requests, sleep if needed)
  - Handle errors (timeout, invalid key, rate limit exceeded)
- [ ] Implement ticker-based querying
  - Create priority list: top 50 companies by market cap
  - Query Finnhub for these 50 companies
  - Query Alpha Vantage for top 100 companies
- [ ] Build CIK lookup table
  - Download: `https://www.sec.gov/files/company_tickers.json`
  - Create mapping: ticker → CIK
  - Store in `companies` table (via init.sql or migration)
- [ ] Implement SEC EDGAR RSS parser
  - Generate feed URLs for all 500 companies
  - Parse Atom feed format
  - Filter for important filings (8-K, 10-K, 10-Q, Form 4)
- [ ] Add all sources to scheduler (in ingestion worker)
  - RSS: every 15 minutes
  - Finnhub: every 4 hours (staggered)
  - Alpha Vantage: once daily
  - SEC: every 2 hours
- [ ] Add basic monitoring
  - Count articles fetched per source
  - Log errors to stdout (captured by Docker)
  - Alert if source fails >3 times in a row (email or console)
- [ ] **Update ingestion-worker Dockerfile**
  - Rebuild with new dependencies
  - Test locally: `docker-compose build ingestion-worker`
  - Restart: `docker-compose up -d ingestion-worker`

**Deliverables:**
- API clients working within rate limits (inside container)
- SEC EDGAR integration functional
- All sources in scheduler
- Basic error logging and monitoring
- API keys securely passed via environment variables

**Success Criteria:**
- Fetching 1,000+ raw articles/day from all sources
- All API calls succeed (no bans or errors)
- SEC filings captured within 2 hours of publication
- Can see source breakdown in logs (`docker-compose logs ingestion-worker`)
- Container restarts don't lose API keys or configuration
- **Can deploy same setup to cloud without code changes**

**Time Estimate:** 4-5 days

---

### **Phase 1 Checkpoint**

**Before moving to Phase 2:**
- [ ] **Docker Compose setup complete with 2 containers (postgres + ingestion-worker)**
- [ ] `docker-compose up -d` successfully starts all services
- [ ] 1,000+ articles/day being ingested
- [ ] All 3 source types working (RSS, API, SEC)
- [ ] URL deduplication preventing re-ingestion
- [ ] Scheduler running reliably inside container
- [ ] Database growing steadily (persistent volume)
- [ ] Error rate <5%
- [ ] Can rebuild containers without losing data
- [ ] Logs accessible via `docker-compose logs`

**Estimated Total Time:** 8-10 days (includes Docker setup)

---

## **PHASE 2: CORE PROCESSING (WEEK 3-4)**

### **Goal**
Extract full text, identify S&P 500 companies in articles, calculate sentiment.

### **Week 3: Content Extraction + Named Entity Recognition (New Container)**

**Tasks:**
- [ ] **Create new processing-worker container**
  - New directory: `processing-worker/`
  - Separate Dockerfile with NLP dependencies
  - Add to docker-compose.yml
- [ ] **Build processing-worker Dockerfile**
  - Install NLP libraries: `spacy`, `newspaper3k`
  - Download spaCy model during build: `RUN python -m spacy download en_core_web_sm`
  - Small model (13MB), fast, good enough for MVP
  - Copy processing source code
- [ ] **Update docker-compose.yml**
  - Add processing-worker service
  - Connect to same database
  - Share network with other services
  - Set restart policy: `always`
- [ ] Write content extraction module (in processing-worker)
  - Use newspaper3k to fetch full article text
  - Handle timeouts (10 second limit)
  - If fails, use RSS summary as fallback
  - Store cleaned text in `articles_processed` table
- [ ] Build company name normalization database
  - For each S&P 500 company, create variations:
    - Official name: "Apple Inc."
    - Short name: "Apple"
    - Ticker: "AAPL"
    - Common aliases: "iPhone maker", "Cupertino tech giant"
  - Store in `company_aliases` table
- [ ] Implement NER pipeline
  - Load spaCy model
  - Extract ORGANIZATION entities from article text
  - Match entities against company_aliases database
  - Use fuzzy matching (>90% similarity) for variations
- [ ] Calculate mention statistics
  - Count mentions in title
  - Count mentions in first paragraph
  - Count mentions in body
- [ ] Store results in `entity_mentions` table
  - Columns: article_id, company_id, title_mentions, body_mentions, total_mentions
- [ ] Filter articles
  - Keep only articles mentioning at least one S&P 500 company
  - Discard others (mark as irrelevant, don't process further)

**Deliverables:**
- Separate processing-worker container running NLP pipeline
- Content extraction working for >80% of articles
- NER identifying companies in articles
- Company name matching working (manual testing on sample articles)
- Filtered dataset (S&P 500 mentions only)

**Success Criteria:**
- Extract full text from 80%+ of articles
- Correctly identify company mentions with 80%+ accuracy (manual spot check)
- Filter down to ~800-1,000 S&P 500-relevant articles/day
- Processing keeps up with ingestion (no backlog)
- Processing worker runs independently in its own container
- Can scale processing by running multiple container instances if needed
- `docker-compose ps` shows all 3 services running (db, ingestion, processing)

**Time Estimate:** 5-6 days

---

### **Week 4: Sentiment Analysis + Basic Scoring**

**Tasks:**
- [ ] Install sentiment library: `vaderSentiment`
  - Rule-based, no ML training needed
  - Specifically designed for financial/social text
  - Fast, lightweight
- [ ] Implement sentiment analysis
  - Analyze full article text
  - Get compound score (-1 to +1)
  - Classify: positive (>0.05), negative (<-0.05), neutral (between)
- [ ] Calculate entity-specific sentiment (optional for MVP)
  - Extract sentences mentioning each company
  - Analyze sentiment per sentence
  - Aggregate to company-level sentiment
  - **Skip if time is short** - use overall article sentiment for MVP
- [ ] Store sentiment in database
  - Add columns to `articles_processed`: sentiment_score, sentiment_label
  - If doing entity-level: add to `entity_mentions` table
- [ ] Implement simple relevance score (0-100)
  - **Simple formula for MVP:**
    ```
    Score = 
      Title mention: 40 points
      + First paragraph mention: 20 points
      + Body mentions: min(5 × count, 20) points
      + Is SEC filing: 20 points
      + Source quality: 10 points (hard-code tier 1 sources)
    Max = 100 points
    ```
- [ ] Store relevance scores in `entity_mentions` table
- [ ] Add indexes to database
  - Index on: company_id, published_at, relevance_score, sentiment_score
  - These will speed up API queries

**Deliverables:**
- Sentiment analysis working on all articles
- Simple relevance scoring implemented
- Database indexed for fast queries
- Processing pipeline end-to-end functional

**Success Criteria:**
- Sentiment scores calculated for all articles
- Spot-check accuracy: positive news scores positive, negative news scores negative
- Relevance scores make intuitive sense (high score = clearly about company)
- Can process 1,000 articles/day without lag

**Time Estimate:** 4-5 days

---

### **Phase 2 Checkpoint**

**Before moving to Phase 3:**
- [ ] **3 containers running (postgres + ingestion-worker + processing-worker)**
- [ ] Full processing pipeline working
- [ ] Articles have extracted text, identified companies, sentiment, relevance
- [ ] ~800 S&P 500-relevant articles/day being processed
- [ ] Database has indexed processed articles
- [ ] Processing time <5 minutes per article on average
- [ ] Processing worker runs independently in its own container
- [ ] All services communicate via Docker internal network

**Estimated Total Time:** 9-11 days

---

## **PHASE 3: SIMPLE STORAGE (WEEK 5)**

### **Goal**
Finalize database schema, add full-text search, implement data retention.

### **Week 5: Database Optimization**

**Tasks:**
- [ ] Create final database schema
  - **companies table:**
    ```sql
    CREATE TABLE companies (
      id SERIAL PRIMARY KEY,
      ticker VARCHAR(10) UNIQUE NOT NULL,
      name VARCHAR(255) NOT NULL,
      sector VARCHAR(100),
      industry VARCHAR(100),
      market_cap BIGINT,
      cik VARCHAR(10)
    );
    ```
  - **articles table:**
    ```sql
    CREATE TABLE articles (
      id SERIAL PRIMARY KEY,
      url TEXT UNIQUE NOT NULL,
      title TEXT NOT NULL,
      summary TEXT,
      content TEXT,
      published_at TIMESTAMP NOT NULL,
      fetched_at TIMESTAMP NOT NULL,
      source_name VARCHAR(100),
      source_type VARCHAR(20),
      sentiment_score FLOAT,
      sentiment_label VARCHAR(10),
      processed BOOLEAN DEFAULT FALSE
    );
    CREATE INDEX idx_articles_published ON articles(published_at DESC);
    CREATE INDEX idx_articles_sentiment ON articles(sentiment_score);
    ```
  - **entity_mentions table:**
    ```sql
    CREATE TABLE entity_mentions (
      id SERIAL PRIMARY KEY,
      article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
      company_id INTEGER REFERENCES companies(id),
      title_mentions INTEGER DEFAULT 0,
      body_mentions INTEGER DEFAULT 0,
      relevance_score INTEGER,
      entity_sentiment FLOAT
    );
    CREATE INDEX idx_mentions_company ON entity_mentions(company_id, relevance_score DESC);
    CREATE INDEX idx_mentions_article ON entity_mentions(article_id);
    ```
- [ ] Set up PostgreSQL full-text search
  - Enable pg_trgm extension: `CREATE EXTENSION pg_trgm;`
  - Create GIN index on article title and content:
    ```sql
    CREATE INDEX idx_articles_fts ON articles 
    USING GIN (to_tsvector('english', title || ' ' || COALESCE(content, '')));
    ```
- [ ] Implement data retention policy
  - Keep last 30 days of articles
  - Weekly cleanup job: delete articles older than 30 days
  - Keep SEC filings indefinitely (they're rare and important)
- [ ] Add database backup script
  - Daily PostgreSQL dump to file
  - Keep last 7 days of backups
  - Store on separate volume or cloud storage
- [ ] Database performance tuning
  - Set appropriate `shared_buffers` (25% of RAM)
  - Enable query logging for slow queries (>1 second)
  - Run ANALYZE to update statistics
- [ ] Write data migration script
  - Move data from temporary tables to final schema
  - Verify data integrity

**Deliverables:**
- Final database schema in production
- Full-text search working
- Backup script scheduled
- Data retention policy implemented

**Success Criteria:**
- Can search articles by keyword in <500ms
- Database queries return results in <200ms
- Backups running daily
- Old data being cleaned up automatically

**Time Estimate:** 5-6 days

---

### **Phase 3 Checkpoint**

**Before moving to Phase 4:**
- [ ] Database schema finalized and optimized
- [ ] Full-text search functional
- [ ] Indexes on all query columns
- [ ] Backup and retention policies active
- [ ] Database can handle expected query load

**Estimated Total Time:** 5-6 days

---

## **PHASE 4: BASIC API (WEEK 6)**

### **Goal**
Build REST API with 5 core endpoints for your trading dashboard.

### **Week 6: FastAPI Development (Containerized API)**

**Tasks:**
- [ ] **Create API container**
  - New directory: `api/`
  - FastAPI application structure:
    ```
    api/
    ├── Dockerfile
    ├── main.py
    ├── database.py
    ├── models.py (Pydantic)
    ├── routers/
    │   ├── stories.py
    │   ├── companies.py
    │   └── health.py
    └── requirements.txt
    ```
- [ ] **Build API Dockerfile**
  - Base: python:3.11-slim
  - Install: fastapi, uvicorn, sqlalchemy, psycopg2-binary, pydantic
  - Expose port 8000
  - CMD: `uvicorn main:app --host 0.0.0.0 --port 8000`
- [ ] **Update docker-compose.yml**
  - Add API service
  - Expose port 8000:8000 (only external-facing port)
  - Connect to database via internal network
  - Set restart policy
  - Add healthcheck: `curl -f http://localhost:8000/health || exit 1`
- [ ] Configure database connection (SQLAlchemy)
  - Connection string from environment variable
  - Use Docker service name: `postgresql://user:pass@postgres:5432/newsagg`
- [ ] Implement 5 core endpoints:

**1. GET /health**
- Simple health check
- Returns: `{"status": "ok", "timestamp": "..."}`

**2. GET /companies**
- List all S&P 500 companies
- Query params: `sector` (optional filter)
- Returns: Array of companies with ticker, name, sector

**3. GET /stories**
- Main endpoint for searching articles
- Query params:
  - `tickers`: comma-separated (e.g., "AAPL,MSFT,GOOGL")
  - `start_date`: ISO date (default: 7 days ago)
  - `end_date`: ISO date (default: today)
  - `min_relevance`: 0-100 (default: 50)
  - `sentiment`: "positive" | "negative" | "neutral" | "all" (default: all)
  - `limit`: 1-100 (default: 20)
  - `offset`: for pagination (default: 0)
- Returns: Array of articles with:
  - id, title, summary, url, published_at, source
  - companies: array of {ticker, name, relevance, sentiment}
  - overall_sentiment
- Example response:
  ```json
  {
    "results": [
      {
        "id": 123,
        "title": "Apple Reports Strong Q4 Earnings",
        "summary": "Apple Inc. exceeded analyst expectations...",
        "url": "https://...",
        "published_at": "2024-01-15T10:30:00Z",
        "source": "Reuters",
        "companies": [
          {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "relevance": 95,
            "sentiment": 0.7
          }
        ],
        "overall_sentiment": 0.7
      }
    ],
    "total": 127,
    "limit": 20,
    "offset": 0
  }
  ```

**4. GET /companies/{ticker}/stories**
- Convenience endpoint for single company
- Same as `/stories?tickers={ticker}`
- Query params: `start_date`, `end_date`, `min_relevance`, `limit`, `offset`

**5. GET /companies/{ticker}/sentiment**
- Get sentiment trend over time
- Query params:
  - `days`: 7, 14, or 30 (default: 7)
- Returns: Daily sentiment averages
- Example response:
  ```json
  {
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "period": "7d",
    "data": [
      {
        "date": "2024-01-15",
        "avg_sentiment": 0.65,
        "article_count": 12,
        "positive": 8,
        "negative": 2,
        "neutral": 2
      }
      // ... more days
    ],
    "overall_avg": 0.58
  }
  ```

- [ ] Add input validation (Pydantic models)
- [ ] Add error handling (404, 400, 500)
- [ ] Add basic API key authentication
  - Single hardcoded API key for MVP
  - Check `X-API-Key` header
  - Return 401 if missing or invalid
- [ ] Generate OpenAPI documentation (automatic with FastAPI)
- [ ] Add CORS configuration (allow requests from your dashboard domain)
- [ ] Write basic tests for each endpoint

**Deliverables:**
- FastAPI application running in dedicated container
- 5 endpoints functional and tested
- OpenAPI docs at `/docs`
- Simple authentication working
- API accessible via http://localhost:8000 locally

**Success Criteria:**
- All endpoints return correct data
- Query by ticker returns relevant articles
- Sentiment endpoint shows trends
- Response time <500ms for typical queries
- API documentation is clear and complete
- **API container can be accessed from external application**
- **Can curl API from host machine: `curl http://localhost:8000/health`**
- Container logs show incoming requests
- API automatically restarts on failure

**Time Estimate:** 6-7 days

---

### **Phase 4 Checkpoint**

**Before moving to Phase 5:**
- [ ] **4 containers running (postgres + ingestion-worker + processing-worker + api)**
- [ ] All 5 core endpoints working
- [ ] Can query articles by ticker, date range, sentiment
- [ ] API is documented (OpenAPI at /docs)
- [ ] Basic authentication in place (X-API-Key header)
- [ ] Response times acceptable (<500ms)
- [ ] **API accessible from host machine: `curl http://localhost:8000/health`**
- [ ] **Your trading dashboard can connect and fetch data from the containerized API**
- [ ] Only port 8000 is exposed externally
- [ ] All containers restart automatically on failure

**Estimated Total Time:** 6-7 days

---

## **PHASE 5: ESSENTIAL FEATURES (WEEK 7-8)**

### **Goal**
Add minimal polish: basic monitoring, simple deployment, essential documentation.

### **Week 7: Monitoring & Reliability**

**Tasks:**
- [ ] Add logging throughout application
  - Use Python `logging` module
  - Log levels: INFO for normal operations, WARNING for issues, ERROR for failures
  - Log format: timestamp, level, module, message
  - Log to both console and file
- [ ] Create simple monitoring dashboard
  - Option 1: Simple HTML page with stats
  - Option 2: Use Grafana (if you have time)
  - Show:
    - Articles ingested today/week
    - Articles per source
    - Processing success rate
    - API request count
    - Database size
- [ ] Add health checks
  - Database connection check
  - Disk space check (warn if <10GB free)
  - Last successful ingestion check (warn if >2 hours ago)
- [ ] Implement basic alerting
  - Send email if:
    - No articles ingested for 3 hours
    - Database connection fails
    - Disk space <5GB
  - Use Python `smtplib` for email
  - Or use a service like Mailgun (free tier)
- [ ] Add error recovery
  - If source fails, retry 3 times with exponential backoff
  - If still fails, log error and continue with other sources
  - Don't crash the entire system for one bad source

**Deliverables:**
- Comprehensive logging throughout application
- Basic monitoring dashboard or metrics endpoint
- Email alerts for critical issues
- Error recovery mechanisms

**Success Criteria:**
- Can see system health at a glance
- Get notified of problems within 15 minutes
- System recovers automatically from transient failures
- Logs are useful for debugging issues

**Time Estimate:** 4-5 days

---

### **Week 8: Documentation & Cloud Deployment**

**Tasks:**
- [ ] Write comprehensive README.md
  - Project overview
  - Architecture diagram showing all containers
  - **Local setup: Quick start with Docker Compose**
    ```bash
    cp .env.example .env
    # Edit .env with your API keys
    docker-compose up -d
    ```
  - Configuration options (all via environment variables)
  - How to run locally
  - **How to deploy to cloud (Docker Compose)**
  - **How external apps connect to the API**
- [ ] Write API documentation
  - How to authenticate (X-API-Key header)
  - Example requests for each endpoint (with curl)
  - Response format specifications
  - Error codes and meanings
  - Connection URL for external applications
- [ ] Document operational procedures
  - How to check system health: `docker-compose ps`
  - How to view logs: `docker-compose logs -f [service]`
  - How to restart services: `docker-compose restart [service]`
  - How to rebuild: `docker-compose build [service]`
  - How to restore from backup
  - How to add a new data source
- [ ] **Finalize production docker-compose.yml**
  ```yaml
  version: '3.8'
  services:
    postgres:
      image: postgres:15-alpine
      restart: always
      volumes:
        - postgres_data:/var/lib/postgresql/data
        - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
      environment:
        POSTGRES_DB: newsagg
        POSTGRES_USER: newsagg
        POSTGRES_PASSWORD: ${DB_PASSWORD}
      networks:
        - internal
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U newsagg"]
        interval: 10s
        timeout: 5s
        retries: 5

    ingestion-worker:
      build: ./ingestion-worker
      restart: always
      depends_on:
        postgres:
          condition: service_healthy
      environment:
        DATABASE_URL: postgresql://newsagg:${DB_PASSWORD}@postgres:5432/newsagg
        FINNHUB_API_KEY: ${FINNHUB_API_KEY}
        ALPHAVANTAGE_API_KEY: ${ALPHAVANTAGE_API_KEY}
      networks:
        - internal

    processing-worker:
      build: ./processing-worker
      restart: always
      depends_on:
        postgres:
          condition: service_healthy
      environment:
        DATABASE_URL: postgresql://newsagg:${DB_PASSWORD}@postgres:5432/newsagg
      networks:
        - internal

    api:
      build: ./api
      restart: always
      ports:
        - "8000:8000"
      depends_on:
        postgres:
          condition: service_healthy
      environment:
        DATABASE_URL: postgresql://newsagg:${DB_PASSWORD}@postgres:5432/newsagg
        API_KEY: ${API_KEY}
      networks:
        - internal
        - external
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
        interval: 30s
        timeout: 10s
        retries: 3

  networks:
    internal:
      driver: bridge
    external:
      driver: bridge

  volumes:
    postgres_data:
  ```
- [ ] **Create cloud deployment guide**
  - [ ] Choose cloud provider (DigitalOcean, AWS, GCP, Hetzner)
  - [ ] Document VPS setup steps
  - [ ] Document Docker installation
  - [ ] Document how to clone repo and configure .env
  - [ ] Document how to run docker-compose on remote server
  - [ ] Document how to expose API port (firewall rules)
  - [ ] Document how to set up SSL/TLS (optional: nginx reverse proxy)
- [ ] **Deploy to production cloud environment**
  - Rent VPS (Hetzner, DigitalOcean, Linode)
  - 4GB RAM, 2 vCPU, 80GB disk = ~$20-40/month
  - Install Docker and Docker Compose on VPS
  - Clone repository to VPS
  - Create production .env file with secrets
  - Run `docker-compose up -d` (starts all 4 containers)
  - Configure firewall (allow port 8000 for API, 22 for SSH)
  - Optional: Set up nginx reverse proxy + SSL certificate (Let's Encrypt)
- [ ] **Configure external application connectivity**
  - Document API endpoint: `http://your-vps-ip:8000`
  - Or with domain: `https://api.yourdomain.com`
  - Test connection from external network: `curl http://your-vps-ip:8000/health`
  - Provide connection details to your trading dashboard/KG application
- [ ] Test production deployment
  - Verify all 4 containers start: `docker-compose ps`
  - Check ingestion is working: `docker-compose logs -f ingestion-worker`
  - Check processing is working: `docker-compose logs -f processing-worker`
  - Test API from external network (from your other application)
  - Monitor for 24 hours
  - Test auto-restart: `docker-compose restart api` should not cause downtime
- [ ] Create backup and restore scripts
  - Backup script: `pg_dump` to file
  - Restore script: `pg_restore` from file
  - Schedule daily backups via cron
- [ ] Write disaster recovery plan
  - What to do if database corrupts
  - What to do if server crashes
  - How to restore from backup
  - Contact information

**Deliverables:**
- Complete documentation (README, API docs, ops docs, cloud deployment guide)
- Production-ready docker-compose.yml with health checks and restart policies
- Cloud deployment running all 4 containers
- Backup and disaster recovery plan
- Connection instructions for external applications

**Success Criteria:**
- New developer can set up locally in <1 hour: `docker-compose up -d`
- System is running in production cloud environment
- **API is accessible from your trading dashboard/external application**
- **External app can successfully query API endpoints**
- All containers restart automatically on failure
- Backups are running daily (via cron + docker exec)
- You know how to recover from common failures
- Can deploy to new cloud environment in <2 hours by following guide
- **Dev/prod parity: identical Docker Compose setup locally and in cloud**

**Time Estimate:** 5-6 days

---

### **Phase 5 Checkpoint**

**Before declaring MVP complete:**
- [ ] Monitoring shows system is healthy
- [ ] Documentation is complete and accurate (includes Docker deployment guide)
- [ ] **Production deployment in cloud with all 4 containers running**
- [ ] System stable for 3+ days in production
- [ ] **API is serving requests to your trading dashboard from external application**
- [ ] **External app can successfully connect to cloud-hosted API**
- [ ] Backups are being created daily (via Docker exec)
- [ ] You're confident you can maintain this system
- [ ] Can redeploy to new VPS in <2 hours using docker-compose
- [ ] Dev/prod parity maintained (identical Docker setup locally and in cloud)

**Estimated Total Time:** 9-11 days

---

## **MVP INFRASTRUCTURE**

### **Development Environment (Docker-First)**

**Local Development Setup:**
```bash
# Requirements
- Docker Desktop (includes Docker Compose)
- Git
- 8GB RAM minimum (16GB recommended)
- 20GB disk space
- Text editor (VS Code recommended)

# NO need to install:
- ❌ Python locally (runs in containers)
- ❌ PostgreSQL locally (runs in container)
- ❌ Virtual environments (containerized)

# Tools
- VS Code with Docker extension
- Postman or curl (API testing)
- DBeaver or pgAdmin (database browser - connect to localhost:5432)
```

**Docker Compose for Local Dev:**
```yaml
# All services run in containers:
- postgres:5432 (exposed for DB browser)
- api:8000 (exposed for testing)
- ingestion-worker (internal only)
- processing-worker (internal only)
```

**Development Workflow:**
1. Edit code locally in your editor
2. Rebuild container: `docker-compose build [service]`
3. Restart: `docker-compose up -d [service]`
4. Test API via curl or Postman → http://localhost:8000
5. Check database via DBeaver → localhost:5432
6. View logs: `docker-compose logs -f [service]`
7. Debug: `docker-compose exec [service] bash`

**Hot Reload (Optional Enhancement):**
- Mount source code as volume in docker-compose.yml
- API container watches for file changes (uvicorn --reload)
- No rebuild needed for Python code changes

---

### **Production Infrastructure (Single VPS + Docker)**

**Recommended VPS Specs:**
- **Provider:** Hetzner (cheapest), DigitalOcean (easiest), or Linode
- **Specs:** 4GB RAM, 2 vCPU, 80GB SSD
- **Cost:** $20-40/month
- **OS:** Ubuntu 22.04 LTS
- **Software:** Docker + Docker Compose only

**Why Single VPS + Docker Compose Is Enough:**
- MVP handles 1,000 articles/day easily on one machine
- All 4 containers run on single VPS: ~3GB RAM total
- CPU usage low (NLP is batch processed)
- Docker provides isolation, easy restart, and portability
- Can scale later by moving to Docker Swarm or Kubernetes
- **Identical setup locally and in production (dev/prod parity)**

**Single VPS Layout (Containerized):**
```
VPS (4GB RAM, 2 vCPU) running Docker
├── Container: postgres (1.5GB RAM)
│   └── Volume: postgres_data (persistent)
├── Container: ingestion-worker (512MB RAM)
│   └── Connects to postgres via internal network
├── Container: processing-worker (1GB RAM)
│   └── Connects to postgres via internal network
├── Container: api (512MB RAM)
│   ├── Exposes port 8000 externally
│   └── Connects to postgres via internal network
├── Operating System (~500MB RAM)
└── Free RAM buffer (~500MB)

All orchestrated by docker-compose
All restart automatically on failure
Only API port exposed to external applications
```

**External Application Connectivity:**
```
Your Trading Dashboard/KG App
        │
        │ HTTP requests
        │
        ▼
http://your-vps-ip:8000/stories?tickers=AAPL
        │
        ▼
    API Container (port 8000)
        │
        ▼ (internal network only)
    PostgreSQL Container
```

**No Need For:**
- ❌ Kubernetes (overkill for MVP - Docker Compose is sufficient)
- ❌ Load balancer (one API container is enough)
- ❌ Redis (PostgreSQL caching sufficient)
- ❌ Message queue (direct DB writes fine for MVP)
- ❌ CDN (API responses aren't static)
- ❌ Container registry (build on VPS or use Docker Hub free tier)

**Future Scaling Options (When Needed):**
- Scale horizontally: Deploy same docker-compose setup on multiple VPS instances
- Upgrade to Docker Swarm: Built-in orchestration, easy migration from Compose
- Upgrade to Kubernetes: If you need advanced orchestration (only if necessary)

---

### **Deployment Checklist (Docker-Based)**

**Before First Deploy:**
- [ ] Register domain name (optional, can use IP for MVP)
- [ ] Rent VPS (4GB RAM, Ubuntu 22.04)
- [ ] Install Docker Engine on VPS:
  ```bash
  curl -fsSL https://get.docker.com -o get-docker.sh
  sh get-docker.sh
  ```
- [ ] Install Docker Compose on VPS:
  ```bash
  sudo apt-get install docker-compose-plugin
  ```
- [ ] Configure firewall (UFW):
  ```bash
  sudo ufw allow 22/tcp    # SSH
  sudo ufw allow 8000/tcp  # API
  sudo ufw enable
  ```
- [ ] Set up SSH key authentication
- [ ] Install fail2ban (brute force protection)

**First Deployment:**
- [ ] Clone repository to VPS: `git clone <repo> && cd scraperMVP`
- [ ] Create production `.env` file with all secrets:
  ```bash
  cp .env.example .env
  nano .env  # Add API keys, passwords, etc.
  ```
- [ ] **Build all containers:** `docker-compose build`
- [ ] **Start all services:** `docker-compose up -d`
- [ ] Verify all containers running: `docker-compose ps`
- [ ] Check database initialized: `docker-compose logs postgres | grep "database system is ready"`
- [ ] Seed companies table (if not in init.sql): `docker-compose exec postgres psql -U newsagg -f /seed.sql`
- [ ] **Test API endpoint from VPS:** `curl http://localhost:8000/health`
- [ ] **Test API from external machine:** `curl http://your-vps-ip:8000/health`
- [ ] Optional: Set up nginx reverse proxy + SSL (if using domain name)

**Connecting Your External Application:**
- [ ] Note API base URL: `http://your-vps-ip:8000` or `https://api.yourdomain.com`
- [ ] Note API key from .env file
- [ ] Test connection from your trading dashboard:
  ```bash
  curl -H "X-API-Key: your-api-key" \
       http://your-vps-ip:8000/stories?tickers=AAPL
  ```
- [ ] Update external app configuration with API endpoint and key

**Post-Deployment:**
- [ ] Monitor logs for 24 hours: `docker-compose logs -f`
- [ ] Check ingestion working: `docker-compose logs ingestion-worker | grep "SUCCESS"`
- [ ] Check processing working: `docker-compose logs processing-worker | grep "processed"`
- [ ] Test API from external network (from your other application)
- [ ] Set up automated backups (see backup script below)
- [ ] Document connection details for external apps
- [ ] Test container auto-restart: `docker-compose restart api` (should come back up automatically)

---

### **Backup Strategy (Docker-Compatible)**

**Daily PostgreSQL Backup via Docker:**
```bash
#!/bin/bash
# backup.sh - run via cron daily at 2 AM on VPS host
# Place in /root/backup.sh and chmod +x

DATE=$(date +%Y%m%d)
BACKUP_DIR="/root/backups"
mkdir -p $BACKUP_DIR

# Create backup using docker exec
docker exec newsagg-postgres-1 pg_dump -U newsagg newsagg > $BACKUP_DIR/backup_$DATE.sql

# Compress
gzip $BACKUP_DIR/backup_$DATE.sql

# Delete backups older than 7 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete

# Upload to cloud storage (optional)
# aws s3 cp $BACKUP_DIR/backup_$DATE.sql.gz s3://your-bucket/

echo "Backup completed: backup_$DATE.sql.gz"
```

**Set up cron job on VPS:**
```bash
crontab -e
# Add this line:
0 2 * * * /root/backup.sh >> /var/log/backup.log 2>&1
```

**Recovery Process (Docker-Based):**
```bash
# 1. Stop services
cd /path/to/scraperMVP
docker-compose down

# 2. Restore from backup
gunzip /root/backups/backup_20240115.sql.gz
docker-compose up -d postgres  # Start only postgres
sleep 10  # Wait for postgres to be ready

# 3. Restore data
docker exec -i newsagg-postgres-1 psql -U newsagg newsagg < /root/backups/backup_20240115.sql

# 4. Restart all services
docker-compose up -d

# 5. Verify
docker-compose ps
curl http://localhost:8000/health
```

**Disaster Recovery - Complete Rebuild:**
```bash
# If VPS crashes, deploy to new VPS:
1. Rent new VPS, install Docker
2. Clone repository
3. Restore .env file from secure storage
4. docker-compose up -d
5. Restore database from latest backup
6. Update DNS or inform external apps of new IP
7. System should be operational in <1 hour
```

---

## **MVP COST ANALYSIS**

### **Infrastructure Costs (Monthly)**

**Minimum Configuration:**
```
VPS (Hetzner CX21):              €5.39  (~$6)
  - 4GB RAM, 2 vCPU, 80GB SSD
  - Located in Germany or US

Total Infrastructure:            $6/month
```

**Recommended Configuration:**
```
VPS (DigitalOcean Basic):        $24/month
  - 4GB RAM, 2 vCPU, 80GB SSD
  - Easier UI, better support

OR

VPS (Linode Shared 4GB):         $36/month
  - 4GB RAM, 2 vCPU, 80GB SSD
  - Excellent performance

Backblaze B2 (backups):          $0.50/month
  - 100GB storage
  - For offsite backups

Total Infrastructure:            $24.50 - $36.50/month
```

### **API Costs (Monthly)**

**All Free Tiers:**
```
Finnhub (Free):                  $0
Alpha Vantage (Free):            $0
SEC EDGAR (Government):          $0
All RSS feeds:                   $0

Total API Costs:                 $0/month
```

**No Paid APIs Needed for MVP**

### **Tools & Services (Monthly)**

**All Free Options:**
```
Domain name (optional):          $1/month (or use IP)
SSL Certificate:                 $0 (Let's Encrypt)
Email alerts:                    $0 (use Gmail SMTP)
Monitoring:                      $0 (self-hosted or free tier)

Total Tools:                     $0-1/month
```

### **Total Monthly Cost**

**Absolute Minimum:** $6/month (Hetzner VPS only)

**Recommended MVP:** $30-40/month
- Quality VPS ($24-36)
- Offsite backups ($0.50)
- Domain name ($1)
- Buffer for unexpected costs ($5)

**Compare to CityFalcon Commercial:** $300/month

**Your Savings:** $260-270/month (89-90% cost reduction)

---

### **One-Time Costs**

```
Development time (8 weeks):      $0 (your time)
Domain registration (1 year):    $12 one-time
Learning/setup time:             $0

Total One-Time:                  ~$12
```

---

### **Scaling Costs (Future)**

**When you outgrow single VPS:**
```
Upgrade VPS to 8GB RAM:          +$20/month
Add second VPS (workers):        +$40/month
Managed PostgreSQL:              +$15/month
Premium API tiers:               +$50-100/month

Total at scale:                  ~$120-150/month
```

**Still 50% cheaper than CityFalcon at scale**

---

## **MVP SUCCESS CRITERIA**

### **Functional Requirements**

**Must Work:**
- ✅ Ingest 800-1,000 S&P 500-relevant articles per day
- ✅ All 500 companies covered (at least weekly for long-tail, daily for top 100)
- ✅ Company detection accuracy >80%
- ✅ Sentiment analysis working (positive news = positive score)
- ✅ API returns results in <1 second
- ✅ System runs 24/7 without manual intervention
- ✅ Data retention: 30 days of articles

**Nice to Have (Post-MVP):**
- More sophisticated NLP
- Better deduplication
- More data sources
- Advanced analytics

---

### **Performance Requirements**

**MVP Targets:**
- Ingestion lag: <30 minutes from publication to database
- Processing speed: 1,000 articles/day = ~42 articles/hour = <90 seconds per article
- API response time: <1 second for typical queries
- Uptime: >95% (allows for occasional restarts)
- Error rate: <10% of ingestion attempts

**These are achievable on single VPS**

---

### **Quality Requirements**

**Spot-Check Testing:**
- Pick 10 random articles about Apple
  - Should all have "AAPL" entity detected
  - Relevance scores should be 60-100
  - Sentiment should match article tone
- Query API for "AAPL" in last 7 days
  - Should return 20+ articles (depending on news cycle)
  - Articles should actually be about Apple
  - No duplicates (same URL)
- Test sentiment endpoint
  - Should show trend (not all days identical)
  - Positive/negative counts should add up

**Manual validation on 50-100 articles is sufficient for MVP**

---

### **Operational Requirements**

**You should be able to:**
- Check system health in <2 minutes
- Restart services if needed
- Restore from backup in <30 minutes
- Add a new RSS feed in <10 minutes
- Debug an ingestion failure using logs
- Explain to your team how the system works

**Documentation should enable:**
- New developer to set up locally in <1 hour
- Operations person to maintain system with minimal training

---

## **POST-MVP ROADMAP**

### **Month 3-4: Quality Improvements**

**After MVP is proven stable, add:**
- [ ] Better deduplication (content-based, not just URL)
- [ ] Improved company detection (handle indirect mentions)
- [ ] Entity relationship extraction (Apple + supplier = supply chain link)
- [ ] Historical data beyond 30 days (6 months or 1 year)
- [ ] Elasticsearch for advanced search (if PostgreSQL full-text insufficient)

---

### **Month 5-6: Additional Sources**

**Once core system is solid:**
- [ ] Add 5-10 more RSS feeds
- [ ] Upgrade to paid API tiers (Polygon.io $29/month)
- [ ] Add web scraping for company IR pages
- [ ] Consider earnings call transcripts
- [ ] Add financial blogs (Seeking Alpha authors, Substack)

**Target: 2,000-3,000 articles/day**

---

### **Month 7-8: Advanced Features**

**When you need more sophistication:**
- [ ] Fine-tune NER model on financial text
- [ ] Train custom sentiment model (FinBERT)
- [ ] Add event detection (earnings, M&A, product launches)
- [ ] Implement trending detection
- [ ] Add historical analytics endpoints
- [ ] Real-time alerts for breaking news

---

### **Month 9-12: Scale & Polish**

**If usage grows:**
- [ ] Scale to multiple VPS instances
- [ ] Add load balancer
- [ ] Implement caching (Redis)
- [ ] Add message queue (Kafka or RabbitMQ)
- [ ] Migrate to managed services (RDS, OpenSearch)
- [ ] Advanced monitoring (Datadog, Prometheus)

**Target: 5,000-10,000 articles/day**

---

## **CRITICAL SUCCESS FACTORS**

### **What Will Make or Break This MVP**

**Do These Well:**
1. **Start Simple:** Don't over-engineer. Basic Python scripts are fine.
2. **Test Early:** Query your API from day 1 of Phase 4. Don't wait until the end.
3. **Monitor Constantly:** If ingestion breaks, you need to know immediately.
4. **Document Everything:** Future you (in 2 weeks) will forget how this works.
5. **Focus on Data Quality:** 500 good articles > 2,000 garbage articles.

**Avoid These Traps:**
1. **Premature Optimization:** Don't add Kafka/Redis/Elasticsearch in MVP.
2. **Feature Creep:** Resist adding "just one more data source" before MVP launch.
3. **Perfect Code:** MVP code doesn't need to be beautiful, just functional.
4. **Over-Reliance on Paid APIs:** Use free sources primarily, paid as supplement.
5. **Ignoring Legal Issues:** Read ToS for all sources, respect rate limits.

---

## **FINAL CHECKLIST**

### **Before Declaring MVP Complete**

**Functional:**
- [ ] Ingesting 800+ S&P 500-relevant articles daily
- [ ] All 500 companies have at least weekly coverage
- [ ] Company detection working (80%+ accuracy)
- [ ] Sentiment scores calculated
- [ ] API with 5 core endpoints functional
- [ ] **Your trading dashboard/external app can query the API successfully**
- [ ] **API responds to external requests from your other application**

**Technical:**
- [ ] **All 4 containers running in production (postgres, ingestion, processing, api)**
- [ ] Database optimized and indexed (inside postgres container)
- [ ] System runs 24/7 without manual intervention
- [ ] Containers restart automatically on failure
- [ ] Logs are clear and useful (accessible via docker-compose logs)
- [ ] Monitoring shows system health (docker-compose ps + healthchecks)
- [ ] Alerts configured for critical failures

**Operational:**
- [ ] Documentation complete (README, API docs, ops guide, **Docker deployment guide**)
- [ ] Backup script running daily (via cron + docker exec)
- [ ] Disaster recovery plan written (includes Docker restore process)
- [ ] You know how to maintain the system (docker-compose commands)
- [ ] Production deployment stable for 1+ week
- [ ] **Can deploy to new cloud environment in <2 hours**
- [ ] **External applications know how to connect to API endpoint**

**Quality:**
- [ ] Spot-check on 50 articles shows good quality
- [ ] No major bugs or crashes
- [ ] API responses are fast (<1 second)
- [ ] Data looks correct when browsed manually

**Business:**
- [ ] Cost is <$100/month
- [ ] You can start building your Knowledge Graph on top of this data
- [ ] System provides value to your trading dashboard
- [ ] You're confident this is sustainable long-term

---

## **CONCLUSION**

### **What You're Building**

An **8-week MVP** that aggregates financial news for S&P 500 companies at **<$100/month**, providing:
- 800-1,000 relevant articles/day
- Company detection with 80%+ accuracy
- Sentiment analysis
- Fast REST API (<1 second responses)
- 30 days of searchable history

**This is enough to start building your Knowledge Graph layer.**

---

### **Expected Outcomes**

**Week 8:**
- ✅ System running in production
- ✅ API serving your trading dashboard
- ✅ Ingesting news reliably
- ✅ Costs under control

**Week 12 (After 1 Month in Production):**
- ✅ Stable, proven system
- ✅ Identified areas for improvement
- ✅ Data quality validated
- ✅ Ready to build on top of this foundation

**Month 6:**
- ✅ Refined and optimized
- ✅ Additional sources added
- ✅ Knowledge Graph utilizing news data
- ✅ Trading insights being generated

---

### **Your Competitive Advantage**

**You're not competing with CityFalcon on breadth.**
They cover 300k entities globally in 50+ languages.

**You're competing on depth for S&P 500.**
Your Knowledge Graph with supply chains, competitive intelligence, and causal reasoning is your differentiator.

**This news aggregation system is your data pipeline.**
It feeds your unique technology. Keep it simple, reliable, and focused.

---

### **Next Steps**

1. **Download this plan** (you are here)
2. **Set up development environment** (Docker, PostgreSQL, Python)
3. **Start Week 1** (RSS aggregator)
4. **Follow the checkpoints**
5. **Launch MVP in 8 weeks**
6. **Iterate based on real usage**

**Good luck! You've got a solid plan. Now execute.**

---

## **APPENDIX: KEY RESOURCES**

### **Documentation Links**

- **feedparser (RSS parsing):** https://feedparser.readthedocs.io/
- **spaCy (NER):** https://spacy.io/usage
- **VADER Sentiment:** https://github.com/cjhutto/vaderSentiment
- **newspaper3k (content extraction):** https://newspaper.readthedocs.io/
- **FastAPI (API framework):** https://fastapi.tiangolo.com/
- **PostgreSQL full-text search:** https://www.postgresql.org/docs/current/textsearch.html

### **API Registration Links**

- **Finnhub:** https://finnhub.io/register
- **Alpha Vantage:** https://www.alphavantage.co/support/#api-key
- **SEC EDGAR:** https://www.sec.gov/edgar (no registration needed)

### **S&P 500 Data Sources**

- **Wikipedia list:** https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
- **SEC CIK lookup:** https://www.sec.gov/files/company_tickers.json

### **Hosting Providers**

- **Hetzner (cheapest):** https://www.hetzner.com/cloud
- **DigitalOcean (easiest):** https://www.digitalocean.com/pricing
- **Linode (reliable):** https://www.linode.com/pricing

---

**END OF DOCUMENT**

---