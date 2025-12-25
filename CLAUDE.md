# S&P 500 News Aggregation System - Project Context

**Last Updated**: 2025-12-25

## Project Overview

A production-grade news aggregation and deduplication system for S&P 500 companies. The system ingests financial news from multiple sources (RSS feeds, APIs, SEC filings), stores them in PostgreSQL, and uses **semantic embeddings clustering** to identify duplicate/related articles across sources.

### Architecture: Archive-First

The system follows an **Archive-First** philosophy:
- **All articles are preserved** in `articles_raw` (never deleted)
- **Clustering adds metadata** (cluster labels, centroid flags) rather than removing duplicates
- **Audit trail** via `article_clusters` table tracks all clustering decisions
- **Filtering is additive** - articles marked but never discarded

### Deployment Status

| Environment | Status | Details |
|-------------|--------|---------|
| **Digital Ocean Droplet** | RUNNING | 2 CPU / 4GB RAM, ingestion-worker + postgres + web-dashboard |
| **Local Development** | ACTIVE | Full stack with processing-worker development |
| **Database** | ~50,746 articles | Synced from droplet via `scripts/sync_database_from_droplet.sh` |

---

## Directory Structure

```
scraperMVP/
├── database/                    # PostgreSQL setup
│   ├── Dockerfile
│   └── schema/
│       ├── 01_init.sql         # Core schema (companies, articles_raw)
│       └── 02_seed_companies.sql # S&P 500 data (503 companies)
│
├── ingestion-worker/            # [DEPLOYED] News collection service
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py             # Entry point
│       ├── scheduler.py        # Cron-like task scheduling
│       ├── config.py           # Environment config + RSS feed URLs
│       ├── database.py         # DatabaseManager class
│       ├── logger.py           # Logging setup
│       ├── parsers/
│       │   ├── rss_parser.py                # 10 RSS feeds
│       │   ├── seekingalpha_ticker_parser.py # Ticker-specific SA feeds
│       │   └── sec_parser.py                # SEC EDGAR filings
│       └── api_clients/
│           ├── finnhub_client.py      # Finnhub API
│           ├── alpha_vantage_client.py # Alpha Vantage API
│           ├── sec_cik_mapper.py       # CIK lookup
│           └── sec_parser.py           # SEC parsing
│
├── processing-worker/           # [LOCAL ONLY] Clustering service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── database.py         # ProcessingDatabaseManager
│   │   ├── config.py
│   │   ├── logger.py
│   │   ├── pipeline.py         # (stub - not active)
│   │   └── mechanical_refinery/
│   │       ├── clustering.py   # SentenceEmbeddingClusterer (ACTIVE)
│   │       ├── verb_filter.py  # (not active - future filter layer)
│   │       └── entity_density.py # (not active - future filter layer)
│   │
│   ├── run_clustering_to_db.py      # Cluster recent articles, save to DB
│   ├── cluster_all_articles.py       # Cluster ALL historical articles
│   ├── test_clustering_dry_run.py    # Dry run testing (read-only)
│   └── DEPLOYABILITY_ASSESSMENT.md   # Deployment readiness analysis
│
├── web-dashboard/               # [DEPLOYED] Flask web UI
│   ├── Dockerfile
│   ├── app.py                  # Flask routes + API endpoints
│   └── templates/
│       └── index.html          # Dashboard UI
│
├── scripts/
│   ├── fetch_sp500.py                    # Regenerate S&P 500 seed data
│   └── sync_database_from_droplet.sh     # Pull DB from production
│
├── docker-compose.yml           # Local orchestration
├── .env                         # Environment variables (gitignored)
└── CLAUDE.md                    # THIS FILE
```

---

## Database Schema

### Core Tables

#### `companies` (503 rows)
S&P 500 constituent companies.
```sql
id SERIAL PRIMARY KEY
ticker VARCHAR(10) UNIQUE NOT NULL  -- e.g., "AAPL"
name VARCHAR(255) NOT NULL          -- e.g., "Apple Inc."
sector VARCHAR(100)                 -- e.g., "Technology"
industry VARCHAR(100)               -- e.g., "Consumer Electronics"
cik VARCHAR(10)                     -- SEC CIK for EDGAR lookups
created_at TIMESTAMP
```

#### `articles_raw` (~50,746 rows)
All ingested news articles. **Never deleted**.
```sql
id SERIAL PRIMARY KEY
url VARCHAR(1000) UNIQUE NOT NULL   -- Deduplication key
title TEXT NOT NULL
summary TEXT
source VARCHAR(100) NOT NULL        -- e.g., "Reuters Business", "SEC EDGAR (8-K)"
published_at TIMESTAMP              -- Article publication date
fetched_at TIMESTAMP                -- When we ingested it
raw_json JSONB                      -- Full original data

-- Clustering metadata (populated by processing-worker)
cluster_batch_id UUID               -- Which clustering run
cluster_label INTEGER               -- Cluster ID (-1 = noise/unique)
is_cluster_centroid BOOLEAN         -- TRUE = representative article
distance_to_centroid DOUBLE         -- Similarity distance

-- Future filter metadata (not active yet)
verb_filter_passed BOOLEAN
verb_filter_category VARCHAR
matched_verb VARCHAR
entity_density_passed BOOLEAN
entity_count INTEGER
entity_types_json JSONB
passes_all_filters BOOLEAN
filter_reason VARCHAR
filtered_at TIMESTAMP
```

#### `article_clusters` (~31,000+ rows)
Audit table for clustering decisions. One row per article per clustering batch.
```sql
id SERIAL PRIMARY KEY
cluster_batch_id UUID NOT NULL      -- Links to a clustering run
article_id INTEGER REFERENCES articles_raw(id)
cluster_label INTEGER               -- Cluster assignment
is_centroid BOOLEAN                 -- Is this the cluster representative?
distance_to_centroid DOUBLE         -- Similarity score
clustering_method VARCHAR           -- 'embeddings', 'dbscan', 'minhash'
created_at TIMESTAMP
UNIQUE (cluster_batch_id, article_id)
```

### Other Tables (not actively used)
- `articles_processed` - Legacy processing table
- `mechanical_refinery_results` - Legacy results
- `entity_mentions` - For future entity extraction

---

## Docker Services

### Currently Deployed (Digital Ocean)

```yaml
services:
  postgres:
    container_name: sp500_postgres
    ports: 5432:5432
    volumes: postgres_data (persistent)

  ingestion-worker:
    container_name: sp500_ingestion_worker
    depends_on: postgres
    # Runs scheduler.py continuously

  web-dashboard:
    container_name: sp500_web_dashboard
    ports: 5000:5000
    depends_on: postgres
```

### Not Yet Deployed
- **processing-worker**: Ready but needs automation (cron/scheduler)

---

## Ingestion Schedule (Production)

| Source | Frequency | Details |
|--------|-----------|---------|
| **RSS Feeds** (10) | Every 15 min | Reuters, MarketWatch, Yahoo, SA, Investing.com, CNBC, Benzinga, TechCrunch, The Verge, Bloomberg |
| **Seeking Alpha Tickers** | Every 4 hours | All 503 tickers via `seekingalpha.com/api/sa/combined/{TICKER}.xml` |
| **Finnhub API** | Every 4 hours | Top 50 companies (if API key configured) |
| **Alpha Vantage** | Daily at 6 AM | Top 100 companies (low rate limit) |
| **SEC EDGAR** | Every 2 hours | All companies with CIK |

### Daily Article Volume
- **Average**: ~1,360 non-SEC articles/day
- **Peak**: ~3,000 articles/day (weekdays during market hours)
- **SEC EDGAR**: ~500-1,500 filings/day (excluded from clustering)

---

## Clustering System

### APPROVED: Sentence Embeddings Clustering

**Model**: `all-MiniLM-L6-v2` (384-dim embeddings)
**Algorithm**: Greedy similarity clustering
**Threshold**: 0.78 cosine similarity
**Window**: 36-hour publication windows

```python
from processing_worker.src.mechanical_refinery.clustering import SentenceEmbeddingClusterer

clusterer = SentenceEmbeddingClusterer(
    model_name='all-MiniLM-L6-v2',
    similarity_threshold=0.78,
    min_cluster_size=2
)
result = clusterer.cluster_articles(articles)
```

**Key Scripts**:
- `run_clustering_to_db.py` - Cluster recent 36h window, save to DB
- `cluster_all_articles.py` - Cluster ALL historical articles
- `test_clustering_dry_run.py` - Read-only testing

**Results** (from 31K article test):
- 1,893 displayable clusters (after filtering)
- 10-13% deduplication rate
- 3-4 seconds for 1,600 articles
- Memory: ~1.1 GB peak (fits in 4GB droplet)

### DEPRECATED: DBSCAN Clustering

**Status**: Code exists but **DO NOT USE**. Failed testing due to:
- Poor cluster quality with TF-IDF
- Inconsistent threshold behavior
- Worse performance than embeddings

The `DBSCANClusterer` class remains in code for reference but is not recommended.

### DEPRECATED: MinHash Clustering

**Status**: Code exists but **NOT TESTED**. Lower priority than embeddings.

---

## Web Dashboard API

**Base URL**: `http://localhost:5000` (local) or droplet IP:5000 (production)

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main dashboard HTML |
| `GET /api/articles` | Paginated articles with filters |
| `GET /api/sources` | List sources with counts |
| `GET /api/stats` | Database statistics |
| `GET /api/clusters` | **ALL clusters** across all batches |
| `GET /api/source-breakdown` | Pie chart data |
| `GET /api/health` | Service health check |

### Cluster API Response
```json
{
  "clusters": [
    {
      "batch_id": "uuid",
      "cluster_label": 27,
      "size": 2,
      "avg_similarity": 0.991,
      "articles": [
        {"title": "...", "url": "...", "source": "...", "similarity": 0.98}
      ]
    }
  ],
  "total_clusters": 1893
}
```

---

## Key Configuration

### Environment Variables (.env)
```bash
POSTGRES_HOST=postgres          # 'localhost' for local dev
POSTGRES_PORT=5432
POSTGRES_DB=sp500_news
POSTGRES_USER=scraper_user
POSTGRES_PASSWORD=<secret>

FINNHUB_API_KEY=<optional>
ALPHAVANTAGE_API_KEY=<optional>

FETCH_INTERVAL_MINUTES=15
LOG_LEVEL=INFO
```

### Running Locally with Docker
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f web-dashboard

# Restart after code changes
docker-compose build web-dashboard && docker-compose up -d web-dashboard
```

### Running Clustering Locally
```bash
# Set host for local database
export POSTGRES_HOST=localhost

# Dry run (read-only)
cd processing-worker
python test_clustering_dry_run.py

# Cluster and save to DB
python run_clustering_to_db.py

# Cluster ALL historical data
python cluster_all_articles.py
```

---

## Current State & Next Steps

### What's Working
- Ingestion pipeline (10 RSS + APIs + SEC) on droplet
- PostgreSQL with 50K+ articles
- Web dashboard with cluster viewing
- Embeddings clustering tested on all historical data

### Approved for Development
1. **Processing-worker deployment** - Add to docker-compose, set up cron
2. **Additional filter layer** - User mentioned adding a filter before clustering
3. **Incremental clustering** - Only process new articles (optimization)

### Not Approved / Paused
- DBSCAN clustering (deprecated)
- MinHash clustering (untested)
- Verb filter / entity density filters (future)

---

## Common Tasks

### Sync Database from Production
```bash
./scripts/sync_database_from_droplet.sh
```

### Check Article Counts
```bash
docker exec sp500_postgres psql -U scraper_user -d sp500_news -c \
  "SELECT source, COUNT(*) FROM articles_raw GROUP BY source ORDER BY count DESC LIMIT 10;"
```

### View Recent Clusters
```bash
curl -s http://localhost:5000/api/clusters | python -m json.tool | head -100
```

### Test Clustering Performance
```bash
cd processing-worker
POSTGRES_HOST=localhost python test_clustering_dry_run.py
```

---

## Important Constraints

1. **No deployment to droplet yet** - User wants to add filter layer first
2. **Embeddings only** - DBSCAN is deprecated, don't suggest it
3. **Archive-first** - Never delete articles, only add metadata
4. **SEC EDGAR excluded** - Form 4/8-K filings excluded from clustering (too noisy)
5. **36-hour windows** - Cluster articles published within same 36h period

---

## File Quick Reference

| Need to... | Look at... |
|------------|------------|
| Add new RSS feed | `ingestion-worker/src/config.py` → `RSS_FEEDS` |
| Modify clustering | `processing-worker/src/mechanical_refinery/clustering.py` |
| Add API endpoint | `web-dashboard/app.py` |
| Change database schema | `database/schema/01_init.sql` (+ migration) |
| Debug ingestion | `docker-compose logs ingestion-worker` |
| Run clustering | `processing-worker/run_clustering_to_db.py` |
