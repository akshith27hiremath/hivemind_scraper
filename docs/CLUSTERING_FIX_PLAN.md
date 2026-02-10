# Plan: Fix Classification + Clustering Pipeline & Local Re-Run

## Context

The processing pipeline (classification + incremental clustering) has been running on the production droplet for 46 days without downtime. Investigation revealed:

- **26,330 non-SEC articles permanently orphaned** — classification query filters by `published_at` (2h window) but articles are often fetched days after publication. These articles are never classified, never clustered.
- **Embedding input inconsistency** — initial clustering uses `title` only, but incremental centroid matching uses `title + summary`. 62.6% of FACTUAL articles have no summary, so the inconsistency only affects 37.4% of articles but causes unpredictable matching behavior.
- **Window boundary issues** — 12h bucket normalization creates hard boundaries where articles 6 minutes apart can end up in different groups.
- **Noise articles create excessive batch_ids** — each `mark_as_noise()` call creates a new UUID, producing thousands of unnecessary batch entries.
- **No re-clustering of noise** — articles marked as noise (label=-1) are never revisited, even if a similar article appears later.

**Decision**: Full recluster from scratch with 48h windows, consistent `title`-only embeddings, and the classification bug fixed. Run locally, then upload to cloud.

---

## Phase 1: Fix Code Bugs (Local, No Deployment)

### Fix 1.1: Classification Query — `published_at` → `fetched_at`

**File**: `processing-worker/src/database.py` (line 398-408)

Change `get_unclassified_articles()`:
```python
# BEFORE (line 405):
AND published_at >= %s

# AFTER:
AND fetched_at >= %s
```
Also change the ORDER BY (line 406) and the else branch (line 415-416):
```python
# BEFORE:
ORDER BY published_at DESC

# AFTER:
ORDER BY fetched_at DESC
```

**Why `fetched_at`**: This ensures articles recently ingested (regardless of when they were published) get classified. The scheduler runs hourly with a 2h lookback, so any article fetched in the last 2 hours will be caught.

**Risk**: None — this only affects WHICH unclassified articles are returned, not HOW they're classified.

### Fix 1.2: Consistent Embedding Input — Standardize on `title` Only

**File**: `processing-worker/incremental_clustering.py` (line 231-232)

Change `match_to_centroids()`:
```python
# BEFORE (line 231-232):
article_texts = [f"{a['title']} {a['summary']}" for a in articles]
centroid_texts = [f"{c['title']} {c['summary']}" for c in centroids]

# AFTER:
article_texts = [a['title'] for a in articles]
centroid_texts = [c['title'] for c in centroids]
```

**Why title-only**: The core clustering algorithm (`clustering.py:245`) already uses title-only. Making centroid matching consistent prevents articles from matching centroids they wouldn't have matched during initial clustering. Also, 62.6% of articles have no summary, so title is the only reliable field.

**Risk**: Slightly fewer centroid matches (articles that previously matched via summary context won't match now). This is actually correct — if they wouldn't have clustered together initially, they shouldn't match later.

### Fix 1.3: Window Size — 36h → 48h

**Files**:
- `processing-worker/incremental_clustering.py` (line 31): `WINDOW_HOURS = 48`
- `processing-worker/run_sliding_window_clustering.py` (line 30): `default=48`
- `processing-worker/processing_scheduler.py` — no change needed (uses incremental_clustering's constant)

**Why 48h**: Catches duplicates spanning 2 calendar days (Mon article re-published Tue morning). Minimal false positive increase vs 36h. User-approved.

### Fix 1.4: Fix Window Normalization — 12h → 24h Buckets

**File**: `processing-worker/incremental_clustering.py` (lines 111-114)

```python
# BEFORE:
window_start = article['published_at'].replace(
    hour=(article['published_at'].hour // 12) * 12,
    minute=0, second=0, microsecond=0
)

# AFTER:
window_start = article['published_at'].replace(
    hour=0, minute=0, second=0, microsecond=0
)
```

**Why**: With 48h windows, 24h buckets (one per calendar day) are natural. The centroid search already spans ±WINDOW_HOURS, so the bucket is just for grouping. Articles on the same calendar day should always be in the same bucket.

### Fix 1.5: Reduce Noise Batch Proliferation

**File**: `processing-worker/incremental_clustering.py`

Modify `run_incremental_clustering()` to create ONE noise batch_id per run (not per group):
```python
# At top of function (after line 67):
noise_batch_id = str(uuid.uuid4())

# Pass to mark_as_noise:
mark_as_noise(db, unmatched, noise_batch_id)
```

Modify `mark_as_noise()` signature:
```python
# BEFORE:
def mark_as_noise(db, articles):
    batch_id = str(uuid.uuid4())

# AFTER:
def mark_as_noise(db, articles, batch_id):
    # Use provided batch_id instead of creating new one
```

### Fix 1.6: Remove Redundant Self-Join

**File**: `processing-worker/incremental_clustering.py` (lines 132-142)

```python
# BEFORE:
SELECT
    a.id, a.title, a.summary,
    ar.cluster_batch_id, ar.cluster_label
FROM articles_raw ar
JOIN articles_raw a ON ar.id = a.id
WHERE ar.is_cluster_centroid = TRUE
  AND ar.published_at >= %s
  AND ar.published_at < %s
  AND ar.cluster_label != -1

# AFTER:
SELECT
    id, title, summary,
    cluster_batch_id, cluster_label
FROM articles_raw
WHERE is_cluster_centroid = TRUE
  AND published_at >= %s
  AND published_at < %s
  AND cluster_label != -1
```

---

## Phase 2: Local Re-Run (Classify Orphans + Full Recluster)

### Prerequisites
- Local postgres running with synced production data (already done: 148K articles)
- DistilBERT model available locally at `processing-worker/src/models/bert_classifier/final/`
- Python environment with all dependencies (sentence-transformers, transformers, torch, sklearn, psycopg2)

### Step 2.1: Check if DistilBERT Model Exists Locally

The trained model lives at `processing-worker/src/models/bert_classifier/final/`. This directory is gitignored (weights are too large). If not present locally, we need to SCP it from the droplet:
```bash
scp -r root@159.89.162.233:~/hivemind_scraper/processing-worker/src/models/bert_classifier C:\Programming\scraperMVP\processing-worker\src\models\
```

### Step 2.2: Create Local Re-Run Script

Create `processing-worker/run_local_reprocess.py` that does everything in one shot:

```
Step A: Classify ALL unclassified non-SEC articles (no time window)
  - Query: WHERE classification_label IS NULL AND source NOT LIKE 'SEC EDGAR%'
  - Estimate: 26,341 articles at ~30/sec CPU = ~15 minutes
  - Writes: classification_label, confidence, source, model_version, classified_at, ready_for_kg

Step B: Wipe ALL existing clustering data
  - TRUNCATE article_clusters
  - UPDATE articles_raw SET cluster_batch_id=NULL, cluster_label=NULL,
    is_cluster_centroid=NULL, distance_to_centroid=NULL

Step C: Run sliding window clustering on ALL FACTUAL articles
  - Query: WHERE ready_for_kg = TRUE AND source NOT LIKE 'SEC EDGAR%'
  - Estimate: ~57K FACTUAL articles across ~1,100 48h windows
  - Uses title-only embeddings, threshold 0.5
  - Writes: cluster_batch_id, cluster_label, is_cluster_centroid, distance_to_centroid
  - Also inserts into article_clusters audit table

Step D: Print validation report
  - Total classified vs expected
  - Total clustered vs expected
  - Cluster size distribution
  - Dedup rate
```

**Time estimate**: ~20-30 minutes total on CPU. With XPU (Intel GPU): ~10-15 minutes.

### Step 2.3: Run Locally and Validate

```bash
cd processing-worker
set POSTGRES_HOST=localhost
python run_local_reprocess.py
```

Validate:
- Classification count should be ~86K (existing) + ~13K (newly classified) ≈ 99K non-SEC classified
- FACTUAL count should be ~57K (currently 43.7K + ~13.3K new)
- Cluster count, dedup rate, cluster size distribution should be reasonable
- No articles with cluster_batch_id IS NULL AND ready_for_kg = TRUE

---

## Phase 3: Upload to Cloud

### Step 3.1: Stop Processing Worker on Droplet

```bash
ssh root@159.89.162.233 "cd ~/hivemind_scraper && docker-compose stop processing-worker"
```

**Why**: Prevents the hourly cron from modifying classification/clustering data while we upload. Ingestion-worker can keep running (it only inserts raw articles).

### Step 3.2: Export Local Classification + Clustering Data

Export only the columns we changed (not the entire table):

```bash
# Export classification updates for the 26K orphans
docker exec sp500_postgres psql -U scraper_user -d sp500_news -c "
COPY (
  SELECT id, classification_label, classification_confidence,
         classification_source, classification_model_version,
         classified_at, ready_for_kg
  FROM articles_raw
  WHERE classification_label IS NOT NULL
    AND source NOT LIKE 'SEC EDGAR%'
) TO STDOUT WITH CSV HEADER
" > classification_export.csv

# Export new article_clusters table
docker exec sp500_postgres psql -U scraper_user -d sp500_news -c "
COPY article_clusters TO STDOUT WITH CSV HEADER
" > clusters_export.csv

# Export clustering columns from articles_raw
docker exec sp500_postgres psql -U scraper_user -d sp500_news -c "
COPY (
  SELECT id, cluster_batch_id, cluster_label,
         is_cluster_centroid, distance_to_centroid
  FROM articles_raw
  WHERE cluster_batch_id IS NOT NULL
) TO STDOUT WITH CSV HEADER
" > cluster_status_export.csv
```

### Step 3.3: Upload to Droplet

```bash
scp classification_export.csv clusters_export.csv cluster_status_export.csv \
  root@159.89.162.233:/tmp/
```

### Step 3.4: Apply to Cloud Database

```bash
ssh root@159.89.162.233 << 'SCRIPT'
docker exec -i sp500_postgres psql -U scraper_user -d sp500_news << 'SQL'

-- Step A: Apply classification to orphans
-- Create temp table, load CSV, update matching rows
CREATE TEMP TABLE class_import (
  id INTEGER, classification_label VARCHAR(20),
  classification_confidence DOUBLE PRECISION,
  classification_source VARCHAR(20),
  classification_model_version VARCHAR(50),
  classified_at TIMESTAMP, ready_for_kg BOOLEAN
);
\COPY class_import FROM '/tmp/classification_export.csv' WITH CSV HEADER;

UPDATE articles_raw ar
SET classification_label = ci.classification_label,
    classification_confidence = ci.classification_confidence,
    classification_source = ci.classification_source,
    classification_model_version = ci.classification_model_version,
    classified_at = ci.classified_at,
    ready_for_kg = ci.ready_for_kg
FROM class_import ci
WHERE ar.id = ci.id
  AND ar.classification_label IS NULL;

DROP TABLE class_import;

-- Step B: Wipe old clustering data
TRUNCATE article_clusters;
UPDATE articles_raw SET
  cluster_batch_id = NULL,
  cluster_label = NULL,
  is_cluster_centroid = NULL,
  distance_to_centroid = NULL;

-- Step C: Import new clustering data
CREATE TEMP TABLE cluster_import (
  id SERIAL, cluster_batch_id UUID,
  article_id INTEGER, cluster_label INTEGER,
  is_centroid BOOLEAN, distance_to_centroid DOUBLE PRECISION,
  created_at TIMESTAMP, clustering_method VARCHAR(20)
);
\COPY cluster_import FROM '/tmp/clusters_export.csv' WITH CSV HEADER;

INSERT INTO article_clusters
  (cluster_batch_id, article_id, cluster_label, is_centroid,
   distance_to_centroid, clustering_method, created_at)
SELECT cluster_batch_id, article_id, cluster_label, is_centroid,
       distance_to_centroid, clustering_method, created_at
FROM cluster_import;

DROP TABLE cluster_import;

-- Step D: Import clustering status to articles_raw
CREATE TEMP TABLE status_import (
  id INTEGER, cluster_batch_id UUID, cluster_label INTEGER,
  is_cluster_centroid BOOLEAN, distance_to_centroid DOUBLE PRECISION
);
\COPY status_import FROM '/tmp/cluster_status_export.csv' WITH CSV HEADER;

UPDATE articles_raw ar
SET cluster_batch_id = si.cluster_batch_id,
    cluster_label = si.cluster_label,
    is_cluster_centroid = si.is_cluster_centroid,
    distance_to_centroid = si.distance_to_centroid
FROM status_import si
WHERE ar.id = si.id;

DROP TABLE status_import;

SQL
SCRIPT
```

### Step 3.5: Handle Articles Ingested During Downtime

Between stopping the processing-worker and restarting it, the ingestion-worker continues adding new articles. After uploading:

1. Count new unclassified articles: `SELECT COUNT(*) FROM articles_raw WHERE classification_label IS NULL AND source NOT LIKE 'SEC EDGAR%'`
2. These will be caught by the next classification run (with the fixed `fetched_at` query)

---

## Phase 4: Deploy Fixed Code to Droplet

### Step 4.1: Commit All Changes Locally

Files to commit:
- `processing-worker/src/database.py` (Fix 1.1: fetched_at)
- `processing-worker/incremental_clustering.py` (Fixes 1.2, 1.4, 1.5, 1.6)
- `processing-worker/run_sliding_window_clustering.py` (Fix 1.3: window default)
- `processing-worker/run_local_reprocess.py` (new: local re-run script)

### Step 4.2: Push to Git and Pull on Droplet

```bash
git push origin embeddings_test
ssh root@159.89.162.233 "cd ~/hivemind_scraper && git stash && git pull origin embeddings_test"
```

**Risk**: The droplet has uncommitted changes to `docker-compose.yml` and `requirements.txt`. The `git stash` preserves them. After pull, `git stash pop` may conflict if our commit touched those files. We should commit the droplet's changes first (Phase 1 already captured these locally).

### Step 4.3: Rebuild and Restart Processing Worker

```bash
ssh root@159.89.162.233 "cd ~/hivemind_scraper && docker-compose build processing-worker && docker-compose up -d processing-worker"
```

### Step 4.4: Monitor First Hourly Run

```bash
ssh root@159.89.162.233 "docker logs -f sp500_processing_worker --since=5m"
```

Watch for:
- Classification should find new articles (fetched in last 2h) and classify them
- Clustering should match new FACTUAL articles to existing centroids
- No errors or exceptions
- Verify the 48h window and title-only embeddings in the log output

---

## Phase 5: Validation Queries (Post-Deployment)

```sql
-- 1. No more orphaned non-SEC articles older than 2h
SELECT COUNT(*) FROM articles_raw
WHERE classification_label IS NULL
  AND source NOT LIKE 'SEC EDGAR%'
  AND fetched_at < NOW() - INTERVAL '2 hours';
-- EXPECTED: 0 (was 26,330)

-- 2. All FACTUAL articles should be clustered
SELECT COUNT(*) FROM articles_raw
WHERE ready_for_kg = TRUE
  AND cluster_batch_id IS NULL
  AND source NOT LIKE 'SEC EDGAR%';
-- EXPECTED: Near 0 (only very recent articles waiting for next :05 run)

-- 3. Classification coverage
SELECT classification_label, COUNT(*)
FROM articles_raw
WHERE source NOT LIKE 'SEC EDGAR%'
GROUP BY classification_label;
-- EXPECTED: ~57K FACTUAL, ~37K OPINION, ~5K SLOP, 0 NULL

-- 4. Cluster size distribution should be reasonable
SELECT
  CASE WHEN cnt >= 20 THEN '20+' WHEN cnt >= 5 THEN '5-19'
       WHEN cnt >= 2 THEN '2-4' ELSE '1 (noise)' END as bucket,
  COUNT(*) as num_clusters
FROM (SELECT cluster_batch_id, cluster_label, COUNT(*) as cnt
      FROM article_clusters WHERE cluster_label >= 0
      GROUP BY 1, 2) sub
GROUP BY 1 ORDER BY MIN(cnt);
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DistilBERT model not available locally | Medium | Blocks Phase 2 | SCP from droplet (~500MB) |
| Python dependencies missing locally | Medium | Blocks Phase 2 | `pip install -r requirements.txt` in processing-worker |
| Cloud DB changes during upload window | Low | Data inconsistency | Processing-worker stopped; ingestion-worker only adds new articles (ON CONFLICT DO NOTHING) |
| `git pull` conflict on droplet | Medium | Blocks deploy | `git stash` before pull, resolve after |
| New articles between local sync and upload | Certain | Minor | Fixed classification query catches them on next hourly run |
| Reclustering produces worse results | Low | Quality regression | Compare dedup rate, cluster sizes before/after. Can revert by re-importing old article_clusters |
| Memory issues during 57K article clustering | Low | Crash | Sliding window processes per-window (max ~500-1000 articles at once) |

---

## File Summary

| File | Changes |
|------|---------|
| `processing-worker/src/database.py` | Fix `published_at` → `fetched_at` in `get_unclassified_articles()` |
| `processing-worker/incremental_clustering.py` | Title-only embeddings, 48h window, 24h buckets, single noise batch_id, remove self-join |
| `processing-worker/run_sliding_window_clustering.py` | Default window 48h |
| `processing-worker/run_local_reprocess.py` | **NEW**: Local re-run script (classify orphans + full recluster) |
