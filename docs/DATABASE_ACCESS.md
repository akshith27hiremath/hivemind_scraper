# S&P 500 News Database - Access Guide

## Connection Details

| Property | Value |
|----------|-------|
| **Host** | `159.89.162.233` |
| **Port** | `5432` |
| **Database** | `sp500_news` |
| **User** | `scraper_user` |
| **Password** | `dev_password_123` |

**Connection String:**
```
postgresql://scraper_user:dev_password_123@159.89.162.233:5432/sp500_news
```

---

## Connection Methods

### 1. Command Line (psql)

```bash
psql -h 159.89.162.233 -p 5432 -U scraper_user -d sp500_news
# Password: dev_password_123
```

### 2. Python (psycopg2)

```python
import psycopg2

conn = psycopg2.connect(
    host="159.89.162.233",
    port=5432,
    database="sp500_news",
    user="scraper_user",
    password="dev_password_123"
)

cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM articles_raw")
print(cursor.fetchone())
conn.close()
```

### 3. Python (pandas + SQLAlchemy)

```python
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://scraper_user:dev_password_123@159.89.162.233:5432/sp500_news"
)

# Load FACTUAL articles into DataFrame
df = pd.read_sql("""
    SELECT id, title, summary, source, published_at, url
    FROM articles_raw
    WHERE classification_label = 'FACTUAL'
    ORDER BY published_at DESC
    LIMIT 1000
""", engine)

print(df.head())
```

### 4. GUI Tools (DBeaver, pgAdmin, DataGrip)

Use the connection details from the table above.

---

## Database Schema

### `articles_raw` (~52,000+ rows)

All ingested news articles with classification and clustering metadata.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `url` | VARCHAR | Article URL (unique) |
| `title` | TEXT | Headline |
| `summary` | TEXT | Article summary |
| `source` | VARCHAR | e.g., "Reuters Business", "MarketWatch" |
| `published_at` | TIMESTAMP | Publication date |
| `fetched_at` | TIMESTAMP | When ingested |
| `classification_label` | VARCHAR | `FACTUAL`, `OPINION`, or `SLOP` |
| `classification_confidence` | DOUBLE | 0.0 - 1.0 |
| `ready_for_kg` | BOOLEAN | TRUE if FACTUAL |
| `cluster_label` | INTEGER | Cluster ID (-1 = unique) |
| `is_cluster_centroid` | BOOLEAN | TRUE = representative article |
| `distance_to_centroid` | DOUBLE | Similarity to centroid |

### `article_clusters` (~16,000+ rows)

Clustering audit trail.

| Column | Type | Description |
|--------|------|-------------|
| `cluster_batch_id` | UUID | Clustering run ID |
| `article_id` | INTEGER | FK to articles_raw |
| `cluster_label` | INTEGER | Cluster assignment |
| `is_centroid` | BOOLEAN | Is representative |
| `distance_to_centroid` | DOUBLE | Similarity score |

### `companies` (503 rows)

S&P 500 companies.

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | VARCHAR | e.g., "AAPL" |
| `name` | VARCHAR | e.g., "Apple Inc." |
| `sector` | VARCHAR | e.g., "Technology" |
| `industry` | VARCHAR | e.g., "Consumer Electronics" |

---

## Classification Labels

| Label | Description | Use Case |
|-------|-------------|----------|
| **FACTUAL** | Verifiable news events | Primary data for knowledge graph |
| **OPINION** | Analysis, predictions, commentary | Sentiment analysis |
| **SLOP** | Clickbait, listicles | Usually discard |

**Note:** SEC EDGAR filings are excluded from classification (they're regulatory filings, not news).

---

## Useful Queries

### Classification Distribution
```sql
SELECT
    classification_label,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct
FROM articles_raw
WHERE classification_label IS NOT NULL
GROUP BY classification_label
ORDER BY count DESC;
```

### Get FACTUAL Articles
```sql
SELECT id, title, source, published_at, url
FROM articles_raw
WHERE classification_label = 'FACTUAL'
ORDER BY published_at DESC
LIMIT 100;
```

### Get Cluster Centroids (Deduplicated News)
```sql
SELECT id, title, source, cluster_label, published_at
FROM articles_raw
WHERE is_cluster_centroid = TRUE
ORDER BY published_at DESC;
```

### Get All Articles in a Cluster
```sql
SELECT id, title, source, distance_to_centroid, is_cluster_centroid
FROM articles_raw
WHERE cluster_label = 42  -- replace with cluster ID
ORDER BY is_cluster_centroid DESC, distance_to_centroid ASC;
```

### Source Breakdown
```sql
SELECT source, COUNT(*) as count
FROM articles_raw
GROUP BY source
ORDER BY count DESC;
```

### Recent Articles (Last 24 Hours)
```sql
SELECT id, title, source, classification_label, published_at
FROM articles_raw
WHERE published_at > NOW() - INTERVAL '24 hours'
ORDER BY published_at DESC;
```

### Export to CSV (psql command)
```bash
psql -h 159.89.162.233 -U scraper_user -d sp500_news -c \
  "COPY (SELECT id, title, summary, source, published_at, url
   FROM articles_raw WHERE classification_label = 'FACTUAL')
   TO STDOUT WITH CSV HEADER" > factual_articles.csv
```

---

## Data Notes

- **Hourly updates**: New articles classified at :00, clustered at :05 each hour
- **Cluster label -1**: Article is unique (didn't match any cluster)
- **~50% FACTUAL**: Roughly half of articles are factual news
- **21.9% deduplication**: ~1 in 5 articles are duplicates across sources

---

## Security Note

To close database access:
```bash
ssh root@159.89.162.233
ufw delete allow 5432/tcp
```
