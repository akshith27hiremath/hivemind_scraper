# S&P 500 News Aggregation System - Project Context

**Last Updated**: 2025-12-25

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
**Threshold**: 0.78 cosine similarity
**Window**: 36-hour publication windows
**Input**: FACTUAL articles only (after classification filter)

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

### ✅ Completed (Dec 2025)
1. **Teacher-Student Classification System** - Filters articles into FACTUAL/OPINION/SLOP
2. **Sandbox Web Interface** - Live testing at http://localhost:5050
3. **Database Schema Migration** - Classification columns + teacher_labels table
4. **Training Infrastructure** - Scripts for teacher labeling, student training, dry-run testing

### In Progress
1. **Prompt refinement** - Edge cases like "Analysis with embedded facts" (e.g., Datadog example)
2. **Teacher labeling** - Ready to label 3000-4000 articles once prompt is finalized

### Not Approved / Paused
- DBSCAN clustering (deprecated)
- MinHash clustering (untested)
- Verb filter / entity density filters (future)
- Processing-worker deployment to droplet (waiting for classification deployment)

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

1. **No deployment to droplet yet** - User wants to finalize classification filter first
2. **Embeddings only** - DBSCAN is deprecated, don't suggest it
3. **Archive-first** - Never delete articles, only add metadata
4. **SEC EDGAR excluded** - Form 4/8-K filings excluded from ALL processing (clustering, classification)
5. **36-hour windows** - Cluster articles published within same 36h period
6. **Docker PostgreSQL ONLY** - NEVER use local PostgreSQL installation. Stop it with `net stop postgresql-x64-17` if running. All database access must go through Docker container `sp500_postgres`
7. **Classification before clustering** - Pipeline order: classify → filter FACTUAL → cluster
8. **Headline + Summary** - Teacher classifier sees both for better context (not just headline)

---

## File Quick Reference

| Need to... | Look at... |
|------------|------------|
| Add new RSS feed | `ingestion-worker/src/config.py` → `RSS_FEEDS` |
| Modify clustering | `processing-worker/src/mechanical_refinery/clustering.py` |
| Modify classification prompt | Sandbox: http://localhost:5050 (live editor) OR `teacher_labeler.py` line 30 |
| Test classification | `processing-worker/sandbox_labeler.py` (web UI) |
| Train classifier | `processing-worker/train_student_model.py` |
| Add API endpoint | `web-dashboard/app.py` |
| Change database schema | `database/schema/*.sql` (+ migration) |
| Debug ingestion | `docker-compose logs ingestion-worker` |
| Run clustering | `processing-worker/run_clustering_to_db.py` |
| Label training data | `processing-worker/label_with_teacher.py --num-articles 3000` |
