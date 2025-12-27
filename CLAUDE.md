# S&P 500 News Aggregation System - Project Context

**Last Updated**: 2025-12-27

## Project Overview

A production-grade news aggregation and deduplication system for S&P 500 companies. The system ingests financial news from multiple sources (RSS feeds, APIs, SEC filings), stores them in PostgreSQL, uses **semantic embeddings clustering** to identify duplicate/related articles, and employs **teacher-student classification** to filter out opinion articles and clickbait before clustering.

### Architecture: Archive-First

The system follows an **Archive-First** philosophy:
- **All articles are preserved** in `articles_raw` (never deleted)
- **Clustering adds metadata** (cluster labels, centroid flags) rather than removing duplicates
- **Audit trail** via `article_clusters` table tracks all clustering decisions
- **Filtering is additive** - articles marked but never discarded

### Deployment Status

| Environment | Status | Details |
|-------------|--------|---------|
| **Digital Ocean Droplet** | ✅ FULLY DEPLOYED | 2 CPU / 4GB RAM, all 4 services running |
| **Local Development** | STOPPED | Use droplet for all operations |
| **Database** | ~52,204 articles | 32,670 classified, 16,237 FACTUAL, 2,534 clusters |

### Production URL
- **Web Dashboard**: http://159.89.162.233:5000
- **SSH Access**: `ssh root@159.89.162.233` (password: `.!?UUbdW6C=uMaj`)

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
├── processing-worker/           # [DEPLOYED] Classification + Clustering service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── processing_scheduler.py      # MAIN: Hourly scheduler (runs in Docker)
│   ├── incremental_clustering.py    # Match new articles to existing clusters
│   ├── run_sliding_window_clustering.py  # One-time full clustering
│   ├── run_one_time_classification.py    # One-time full classification
│   ├── src/
│   │   ├── database.py         # ProcessingDatabaseManager
│   │   ├── config.py
│   │   ├── logger.py
│   │   ├── models/             # Trained models
│   │   │   └── bert_classifier/final/  # DistilBERT (86.5% accuracy)
│   │   └── mechanical_refinery/
│   │       ├── clustering.py   # SentenceEmbeddingClusterer
│   │       └── teacher_student/
│   │           ├── bert_classifier.py  # BertClassifier class
│   │           ├── teacher_labeler.py  # GPT-4o labeling
│   │           └── filter.py           # TeacherStudentFilter
│   │
│   ├── train_bert_classifier.py     # Train DistilBERT model
│   ├── label_with_teacher.py        # Generate training labels
│   ├── sandbox_labeler.py           # Web UI for testing
│   └── test_classification_dry_run.py  # Dry run testing
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

#### `articles_raw` (~52,204 rows)
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

-- Classification metadata (populated by processing-worker)
classification_label VARCHAR(20)           -- 'FACTUAL', 'OPINION', 'SLOP'
classification_confidence DOUBLE PRECISION -- 0.0-1.0
classification_source VARCHAR(20)          -- 'student' (DistilBERT)
classification_model_version VARCHAR(50)   -- e.g., 'distilbert-base-uncased-v1'
classified_at TIMESTAMP                    -- When classified
ready_for_kg BOOLEAN                       -- TRUE for FACTUAL articles

-- Clustering metadata (populated by processing-worker)
cluster_batch_id UUID               -- Which clustering run
cluster_label INTEGER               -- Cluster ID (-1 = noise/unique)
is_cluster_centroid BOOLEAN         -- TRUE = representative article
distance_to_centroid DOUBLE         -- Similarity distance
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

### All 4 Services Deployed (Digital Ocean)

```yaml
services:
  postgres:
    container_name: sp500_postgres
    ports: 5432:5432
    volumes: postgres_data (persistent)
    healthcheck: pg_isready

  ingestion-worker:
    container_name: sp500_ingestion_worker
    depends_on: postgres (healthy)
    # Runs scheduler.py continuously - fetches news every 15 min

  processing-worker:
    container_name: sp500_processing_worker
    depends_on: postgres (healthy)
    volumes:
      - ./processing-worker/src/models:/app/src/models:ro  # DistilBERT model
    # Runs processing_scheduler.py - classification at :00, clustering at :05

  web-dashboard:
    container_name: sp500_web_dashboard
    ports: 5000:5000
    depends_on: postgres
    # Flask app with cluster viewing
```

### Service Health Check
```bash
ssh root@159.89.162.233
docker-compose ps  # Should show all 4 services "Up"
docker-compose logs -f processing-worker  # Watch classification/clustering
```

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

## Teacher-Student Classification System

**Status**: ✅ Phase 2 Complete - DistilBERT trained (86.50% accuracy)
**Purpose**: Filter out opinion articles and clickbait BEFORE clustering
**Goal**: Only cluster FACTUAL articles for knowledge graph ingestion

### Architecture

```
Articles (50K+)
      │
      ▼
TeacherStudentFilter (STEP 0)
  ├── GPT-4o labels training data (3000 labeled)
  ├── Student classifier (DistilBERT recommended)
  └── 3-way: FACTUAL / OPINION / SLOP
      │
      ▼ (only FACTUAL articles)
SentenceEmbeddingClusterer (STEP 1)
  └── Cluster related news
      │
      ▼
Knowledge Graph (future)
```

### Classification Categories

| Category | Description | Examples |
|----------|-------------|----------|
| **FACTUAL** | Verifiable events, data releases | "Apple Reports Q4 Revenue of $119.6B", "Tesla Appoints New CFO" |
| **OPINION** | Analysis, predictions, commentary | "Why Apple Could Rally 20%", "Stocks Fall Amid Recession Fears" |
| **SLOP** | Clickbait, listicles, vague teasers | "5 AI Stocks to Buy Now", "Is This the Next Amazon?" |

### Training Data (Completed Dec 2025)

**Teacher Labeling Stats**:
- **Total labels**: 3,000 articles
- **Cost**: $4.13 ($1.38 for 1000 + $2.75 for 2000)
- **Time**: ~1.5 hours total
- **Provider**: OpenAI GPT-4o

**Label Distribution**:
| Label | Count | Percentage |
|-------|-------|------------|
| FACTUAL | 1,655 | 55.2% |
| OPINION | 1,117 | 37.2% |
| SLOP | 228 | 7.6% |

**Checkpoint Saving**: Labels saved every 100 articles to prevent data loss

### Student Models

#### ✅ DistilBERT (Recommended - Production)
- **Model**: `distilbert-base-uncased` (66M params)
- **Accuracy**: 86.50% (best model)
- **Speed**: ~65 articles/second (XPU), ~30/sec (CPU)
- **Memory**: ~500MB
- **Location**: `src/models/bert_classifier/final/`
- **Training Time**: 7.5 minutes on Intel XPU

**Per-Class Performance**:
| Class | Precision | Recall | F1-Score |
|-------|-----------|--------|----------|
| FACTUAL | 90.66% | 90.94% | 90.80% |
| OPINION | 82.02% | 83.86% | 82.93% |
| SLOP | 77.50% | 67.39% | 72.09% |

#### Option 2: MPNet Embeddings + LogisticRegression (Legacy)
- **Model**: `all-mpnet-base-v2` (768-dim) + sklearn LogisticRegression
- **Accuracy**: 78.33% (cross-validation: 78.97% ± 1.17%)
- **Speed**: ~200 articles/second (CPU)
- **Memory**: ~440MB
- **Location**: `src/models/student_classifier_v1.pkl`

**Per-Class Performance**:
| Class | Precision | Recall | F1-Score |
|-------|-----------|--------|----------|
| FACTUAL | 87% | 85% | 86% |
| OPINION | 78% | 67% | 72% |
| SLOP | 46% | 85% | 60% |

**Issues**: SLOP has too many false positives, OPINION recall too low

#### Note: DeBERTa-v3-base Not Used
DeBERTa's disentangled attention mechanism requires ~12GB+ VRAM.
8GB XPU is insufficient. DistilBERT achieves similar accuracy with 40% less memory.

### Components

**Teacher Model** (Training Phase):
- **Provider**: OpenAI GPT-4o (Anthropic Claude supported)
- **Cost**: ~$1.38 per 1000 articles
- **Purpose**: Label training data with high accuracy
- **Location**: `processing-worker/src/mechanical_refinery/teacher_student/teacher_labeler.py`

**Student Model** (Production):
- **Architecture**: DistilBERT fine-tuned for 3-class classification (66M params)
- **Accuracy**: 86.50% on held-out test set
- **Location**: `processing-worker/src/models/bert_classifier/final/`

**Filter Class** (Pipeline Integration):
- **Archive-First**: Marks articles, never deletes
- **Database columns**: `classification_label`, `classification_confidence`, `ready_for_kg`
- **Location**: `processing-worker/src/mechanical_refinery/teacher_student/filter.py`

### Database Schema Changes

**New columns on `articles_raw`:**
```sql
classification_label VARCHAR(20)           -- 'FACTUAL', 'OPINION', 'SLOP'
classification_confidence DOUBLE PRECISION -- 0.0-1.0
classification_source VARCHAR(20)          -- 'teacher' or 'student'
classification_model_version VARCHAR(50)   -- Model identifier
classified_at TIMESTAMP                    -- When classified
ready_for_kg BOOLEAN                       -- TRUE for FACTUAL articles
```

**New table `teacher_labels`** (3,000 rows):
- Stores all teacher-generated labels for retraining
- Audit trail for prompt iterations
- Schema: article_id, label, confidence, reasoning, teacher_model, prompt_version

### Training Scripts

**1. Sandbox Web Interface** (Testing & Iteration):
```bash
cd processing-worker
python sandbox_labeler.py --provider openai
# Opens at http://localhost:5050
```
Features:
- Test random articles from database
- Input custom headlines/summaries
- **Live prompt editor** - modify classification rules in real-time
- **Hot-reload** - prompt changes reflect immediately without restart
- Displays headline + summary + classification + reasoning

**2. Teacher Labeling** (Generate Training Data):
```bash
# Estimate cost first
python label_with_teacher.py --estimate-only --num-articles 3000

# Label articles (excludes SEC EDGAR, saves every 100)
python label_with_teacher.py --provider openai --num-articles 3000 --yes
```
Output: Labels saved to `teacher_labels` table with checkpoints every 100 articles

**3. Train Embedding Student Model** (MPNet):
```bash
POSTGRES_HOST=localhost python train_student_model.py
```
Output: `src/models/student_classifier_v1.pkl`

**4. Train BERT Student Model** (DistilBERT - recommended):
```bash
HF_HUB_ENABLE_HF_TRANSFER=0 POSTGRES_HOST=localhost python train_bert_classifier.py --model distilbert-base-uncased
```
Output: `src/models/bert_classifier/final/` (86.50% accuracy)

**5. Dry Run Testing**:
```bash
python test_classification_dry_run.py --num-articles 500 --verbose
```
Output: Classification distribution, accuracy metrics, source breakdown

### Key Design Decisions

1. **Includes headline + summary** - Better context for classification
2. **3-way classification** - More granular than binary KEEP/DISCARD
3. **Teacher-only labeling** - No manual labeling required
4. **Stratified sampling** - Proportional representation from all sources
5. **SEC EDGAR excluded** - Form 4/8-K filings too different from news articles
6. **Archive-first compliant** - Marks articles, never deletes
7. **Checkpoint saving** - Teacher labels saved every 100 articles (max loss: 100)
8. **Upgraded to MPNet** - Changed from MiniLM-L6-v2 to all-mpnet-base-v2 for better quality

### Current Status & Next Steps

**✅ Completed:**
- Database migration applied
- Sandbox with hot-reload and custom input
- Teacher labeling: 3,000 articles labeled ($4.13)
- MPNet student model trained (78.33% accuracy)
- DistilBERT trained (86.50% accuracy) - **RECOMMENDED**
- Checkpoint saving implemented
- Model comparison complete (DistilBERT wins by +8.17%)

**⏭️ Next:**
1. Validate on dry run test with production data
2. Integrate into pipeline.py before clustering
3. Deploy to production

### Cost Analysis

**Teacher Labeling (One-time)**:
- 3,000 articles: $4.13
- Future labels: ~$1.38 per 1,000 articles

**Student Inference (Ongoing)**:
- $0.00 (runs locally on CPU/XPU)
- Speed: ~65 articles/second (XPU), ~30/sec (CPU)

**Comparison**:
- API-only approach: $502/year (1000 articles/day)
- Student model approach: $4.13 one-time
- **Savings**: $498/year (124x cheaper)

---

## Clustering System

### APPROVED: Sentence Embeddings Clustering

**Model**: `all-MiniLM-L6-v2` (384-dim embeddings)
**Algorithm**: Greedy similarity clustering
**Threshold**: 0.5 cosine similarity (production)
**Window**: 36-hour publication windows
**Input**: FACTUAL articles only (after classification filter)

```python
from processing_worker.src.mechanical_refinery.clustering import SentenceEmbeddingClusterer

clusterer = SentenceEmbeddingClusterer(
    model_name='all-MiniLM-L6-v2',
    similarity_threshold=0.5,
    min_cluster_size=2
)
result = clusterer.cluster_articles(articles)
```

### Incremental Clustering (Hourly)

New articles are matched to **existing cluster centroids** before creating new clusters:
1. Fetch recently classified FACTUAL articles (last 2 hours)
2. Group by 36-hour publication windows
3. For each window:
   - Match new articles to existing centroids (similarity ≥ 0.5)
   - Cluster unmatched articles among themselves
   - Mark isolated articles as noise (cluster_label = -1)

**Key Scripts**:
- `processing_scheduler.py` - Hourly automation (runs in Docker)
- `incremental_clustering.py` - Match-to-centroid logic
- `run_sliding_window_clustering.py` - One-time full clustering

**Production Results** (from 16K FACTUAL articles):
- 2,534+ clusters created
- 21.9% deduplication rate (3,542 duplicates)
- 3-4 seconds per 1,600 articles
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

### ✅ FULLY OPERATIONAL (Dec 2025)

**Production System Running at http://159.89.162.233:5000**

| Component | Status | Details |
|-----------|--------|---------|
| **Ingestion** | ✅ Running | 10 RSS + APIs + SEC, ~1,360 articles/day |
| **Classification** | ✅ Running | DistilBERT @ 86.5% accuracy, hourly at :00 |
| **Clustering** | ✅ Running | Incremental matching, hourly at :05 |
| **Web Dashboard** | ✅ Running | Cluster viewing, source analytics |
| **Database** | ✅ Healthy | 52K+ articles, 2,534 clusters |

### Automated Processing Pipeline

The processing-worker runs `processing_scheduler.py` which:
1. **Classification at :00** - Classifies articles from last 2 hours
2. **Clustering at :05** - Clusters FACTUAL articles from last 2 hours
3. **Data freshness**: <1 hour for new articles

**Key Scripts (in processing-worker/):**
- `processing_scheduler.py` - Main hourly scheduler (runs in Docker)
- `incremental_clustering.py` - Matches new articles to existing cluster centroids
- `run_sliding_window_clustering.py` - One-time full clustering
- `run_one_time_classification.py` - One-time full classification

### ✅ Completed (Dec 2025)
1. **Teacher-Student Classification** - 3,000 GPT-4o labels, DistilBERT trained (86.5%)
2. **Production Deployment** - All 4 services running on droplet
3. **Hourly Automation** - Classification and incremental clustering every hour
4. **One-time Historical Processing** - 32,670 articles classified, 16,237 FACTUAL clustered
5. **Database Schema Migration** - Classification + clustering columns applied
6. **Web Dashboard** - Cluster viewing, source analytics, health checks

### Not Approved / Paused
- DBSCAN clustering (deprecated - use embeddings)
- MinHash clustering (untested)
- Verb filter / entity density filters (future)
- Knowledge graph integration (future)

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

1. **Embeddings only** - DBSCAN is deprecated, don't suggest it
2. **Archive-first** - Never delete articles, only add metadata
3. **SEC EDGAR excluded** - Form 4/8-K filings excluded from ALL processing (clustering, classification)
4. **36-hour windows** - Cluster articles published within same 36h period
5. **Docker PostgreSQL ONLY** - NEVER use local PostgreSQL installation. Stop it with `net stop postgresql-x64-17` if running. All database access must go through Docker container `sp500_postgres`
6. **Classification before clustering** - Pipeline order: classify → filter FACTUAL → cluster
7. **Headline + Summary** - Classifier sees both for better context (not just headline)
8. **UUID as string** - Always convert `uuid.uuid4()` to `str()` for psycopg2 compatibility
9. **Production is primary** - Local containers stopped; use SSH to droplet for operations

---

## File Quick Reference

| Need to... | Look at... |
|------------|------------|
| Add new RSS feed | `ingestion-worker/src/config.py` → `RSS_FEEDS` |
| Modify clustering | `processing-worker/src/mechanical_refinery/clustering.py` |
| Modify classification prompt | Sandbox: http://localhost:5050 (live editor) OR `teacher_labeler.py` line 30 |
| Test classification | `processing-worker/sandbox_labeler.py` (web UI) |
| Train classifier | `processing-worker/train_bert_classifier.py` |
| Add API endpoint | `web-dashboard/app.py` |
| Change database schema | `database/schema/*.sql` (+ migration) |
| Debug ingestion | `ssh droplet` → `docker-compose logs -f ingestion-worker` |
| Debug processing | `ssh droplet` → `docker-compose logs -f processing-worker` |
| Run one-time clustering | `processing-worker/run_sliding_window_clustering.py` |
| Run one-time classification | `processing-worker/run_one_time_classification.py` |
| Label training data | `processing-worker/label_with_teacher.py --num-articles 3000` |
| Check scheduler status | `ssh droplet` → `docker-compose logs -f processing-worker` |

---

## Troubleshooting

### Common Issues

**UUID psycopg2 error**: `can't adapt type 'UUID'`
- Fix: Convert UUID to string: `batch_id = str(uuid.uuid4())`

**Web dashboard not updating after code changes**:
```bash
ssh root@159.89.162.233
cd ~/scraperMVP
docker-compose down
docker-compose up -d
```

**Classification/clustering not running**:
```bash
docker-compose logs -f processing-worker  # Check for errors
docker-compose restart processing-worker  # Restart if stuck
```

**Database connection pool exhausted**:
- Check for unclosed connections in code
- Restart processing-worker: `docker-compose restart processing-worker`

### Production SSH Commands

```bash
# Connect to droplet
ssh root@159.89.162.233

# Check all services
docker-compose ps

# View processing logs (classification/clustering)
docker-compose logs -f processing-worker

# Check database stats
docker exec sp500_postgres psql -U scraper_user -d sp500_news -c \
  "SELECT classification_label, COUNT(*) FROM articles_raw WHERE classification_label IS NOT NULL GROUP BY classification_label;"

# Check cluster counts
docker exec sp500_postgres psql -U scraper_user -d sp500_news -c \
  "SELECT COUNT(DISTINCT cluster_batch_id) as batches, COUNT(*) as total FROM article_clusters;"

# Restart a service
docker-compose restart processing-worker

# Rebuild and restart (after code push)
git pull && docker-compose build processing-worker && docker-compose up -d processing-worker
```
