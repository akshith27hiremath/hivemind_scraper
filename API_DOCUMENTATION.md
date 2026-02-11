# REST API v1 Documentation

**Format**: JSON only
**Authentication**: `X-API-Key` header required on all endpoints
**Last Updated**: 2026-02-11

## Access

| Environment | Base URL | API Key |
|-------------|----------|---------|
| **Production (Cloud)** | `http://159.89.162.233:5000/api/v1` | `b44e4bbc5f2ed67406abd9102a210437c93628b9741e0259e06f20c0515ad4ad` |
| **Local Development** | `http://localhost:5000/api/v1` | `a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2` |

Production runs on a DigitalOcean droplet (2 CPU / 4 GB RAM). Local development uses Docker Desktop.

---

## Authentication

All endpoints require a valid API key in the `X-API-Key` header.

```bash
# Production
curl -H "X-API-Key: b44e4bbc...ad4ad" http://159.89.162.233:5000/api/v1/health

# Local
curl -H "X-API-Key: a1b2c3...a1b2" http://localhost:5000/api/v1/health
```

| Scenario | Response |
|----------|----------|
| Missing header | `401` — `{"error": {"code": "UNAUTHORIZED", "message": "Invalid or missing API key"}}` |
| Wrong key | `401` — same |
| Empty key value | `401` — same |
| Key not configured on server | `503` — `{"error": {"code": "API_NOT_CONFIGURED", ...}}` |

Header names are case-insensitive per HTTP spec (`x-api-key` works).

---

## Response Envelope

All responses use a standard JSON envelope.

**Success:**
```json
{
  "data": [ ... ] or { ... },
  "meta": {
    "count": 42,
    "latest_timestamp": "2026-02-10T18:30:00.435370",
    "has_more": true
  }
}
```

**Error:**
```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "Human-readable description"
  }
}
```

Error codes: `UNAUTHORIZED`, `API_NOT_CONFIGURED`, `INVALID_PARAMETER`, `NOT_FOUND`, `INTERNAL_ERROR`.

---

## Endpoints

### 1. GET /api/v1/articles/feed

**Purpose**: Core polling endpoint. Returns deduplicated FACTUAL articles (cluster centroids + unique noise articles) for downstream consumption. Designed for repeated polling every N minutes.

**Query Parameters**:

| Param | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `since` | ISO 8601 string | _(none — starts from beginning)_ | any valid timestamp | Exclusive lower bound on `classified_at`. Accepts `Z` suffix, `+00:00` offset, or date-only. |
| `ticker` | string | _(none)_ | comma-separated tickers | Filter to articles mentioning these companies. e.g. `AAPL,MSFT,GOOGL` |
| `limit` | integer | 100 | 1–500 | Max articles per response. Values outside range are clamped. |

**Cursor Pagination Pattern**:
```
1. First call:   GET /articles/feed?limit=100
2. Get meta.latest_timestamp from response
3. Next call:    GET /articles/feed?since=<latest_timestamp>&limit=100
4. Repeat. When meta.has_more is false, you've caught up.
```

**Article Selection Logic**:
- `ready_for_kg = TRUE` (classified as FACTUAL)
- `is_cluster_centroid = TRUE` OR `cluster_label = -1` (centroid or unique noise)
- `classified_at IS NOT NULL`
- Ordered by `classified_at ASC, id ASC` (deterministic)

**Response Shape** (`data` is an array):
```json
{
  "id": 12345,
  "url": "https://...",
  "title": "Apple Reports Q4 Revenue of $119.6B",
  "summary": "Apple Inc. reported quarterly...",
  "source": "Reuters Business",
  "published_at": "2026-02-10T14:30:00",
  "fetched_at": "2026-02-10T14:45:00.123456",
  "classified_at": "2026-02-10T15:02:00.435370",
  "classification": {
    "label": "FACTUAL",
    "confidence": 0.9711
  },
  "cluster": {
    "batch_id": "c5603d3c-b1e7-470f-9ced-13d4301c1ad6",
    "label": 27,
    "is_centroid": true,
    "cluster_size": 3
  },
  "tickers": ["AAPL"]
}
```

**Field Descriptions**:

| Field | Type | Notes |
|-------|------|-------|
| `id` | integer | Unique article identifier. Stable. |
| `url` | string | Original article URL |
| `title` | string | Article headline |
| `summary` | string | Article summary (empty string if none) |
| `source` | string | e.g. "Reuters Business", "Seeking Alpha (AAPL)", "Bloomberg" |
| `published_at` | ISO string or null | When the article was published |
| `fetched_at` | ISO string | When we ingested it |
| `classified_at` | ISO string | When DistilBERT classified it (used as cursor) |
| `classification.label` | string | Always "FACTUAL" in feed |
| `classification.confidence` | float | 0.0–1.0, model confidence |
| `cluster.batch_id` | UUID string or null | Which clustering run assigned this |
| `cluster.label` | integer | Cluster ID. `-1` = noise (unique article) |
| `cluster.is_centroid` | boolean | True = representative of the cluster |
| `cluster.cluster_size` | integer | Number of articles in this cluster (1 for noise) |
| `tickers` | string array | S&P 500 tickers mentioned in this article. May be empty. |

**Meta Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `count` | integer | Number of articles in this response |
| `latest_timestamp` | ISO string or null | `classified_at` of the last article. Pass as next `since`. |
| `has_more` | boolean | True if `count == limit` (more pages likely) |

**Performance** (tested on 150K article database):

| Scenario | Local | Production |
|----------|-------|------------|
| Typical poll (limit=100) | **20ms** | **222ms** |
| Large batch (limit=500) | **63ms** | **364ms** |
| With ticker filter (limit=50) | **24ms** | **202ms** |
| Empty results (future since) | **<10ms** | **~115ms** |

Production latencies include ~100–200ms network round-trip. A consumer co-located with the droplet would see local-tier times.

---

### 2. GET /api/v1/articles/{id}

**Purpose**: Full article detail with classification, clustering, and entity mapping metadata. Supports ETag caching.

**Path Parameters**:
- `id` (integer, required) — article ID

**Response Shape** (`data` is an object):
```json
{
  "id": 12345,
  "url": "https://...",
  "title": "...",
  "summary": "...",
  "source": "Reuters Business",
  "published_at": "2026-02-10T14:30:00",
  "fetched_at": "2026-02-10T14:45:00.123456",
  "classified_at": "2026-02-10T15:02:00.435370",
  "classification": {
    "label": "FACTUAL",
    "confidence": 0.9711,
    "source": "student",
    "model_version": "bert_final"
  },
  "cluster": {
    "batch_id": "uuid-string",
    "label": 27,
    "is_centroid": true,
    "distance_to_centroid": 0.0,
    "cluster_size": 3
  },
  "entity_mapped_at": "2026-02-11T00:52:50.318436",
  "company_mentions": [
    {
      "ticker": "AAPL",
      "mention_type": "title",
      "match_method": "name",
      "confidence": 1.0
    }
  ]
}
```

**ETag Caching**: Response includes an `ETag` header. Send `If-None-Match: <etag>` on subsequent requests to receive `304 Not Modified` if unchanged. Articles are immutable after processing, so ETags are long-lived.

**Errors**: `404` if article ID does not exist.

**Performance**: **~10ms** local / **~116ms** production

---

### 3. GET /api/v1/clusters/{batch_id}/{label}

**Purpose**: Retrieve all articles in a specific cluster. Shows what was deduplicated.

**Path Parameters**:
- `batch_id` (UUID string, required) — clustering batch ID
- `label` (integer, required) — cluster label within that batch

**Response Shape**:
```json
{
  "data": {
    "batch_id": "c5603d3c-b1e7-470f-9ced-13d4301c1ad6",
    "label": 41,
    "size": 4,
    "articles": [
      {
        "id": 1962803,
        "title": "US Strikes ISIS in Cooperation With Nigeria",
        "url": "https://...",
        "source": "Bloomberg",
        "published_at": "2025-12-26T16:30:35",
        "is_centroid": true,
        "distance_to_centroid": 0.0,
        "similarity": 1.0,
        "tickers": []
      },
      {
        "id": 2081754,
        "title": "U.S.-backed airstrikes in Nigeria hit two...",
        "url": "https://...",
        "source": "Investing.com",
        "published_at": "2025-12-27T06:30:34",
        "is_centroid": false,
        "distance_to_centroid": 0.2815,
        "similarity": 0.7185,
        "tickers": []
      }
    ]
  }
}
```

Articles are ordered by `distance_to_centroid ASC` (centroid first, then by similarity). Exactly one article in each cluster has `is_centroid: true`.

**Errors**: `400` if batch_id is not a valid UUID. `404` if cluster not found.

**Performance**: **~10ms** local / **~117ms** production

---

### 4. GET /api/v1/companies

**Purpose**: List S&P 500 companies that have article mentions. Useful for discovering available ticker filters.

**Query Parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `sector` | string | _(none)_ | Filter by GICS sector. e.g. `Financials`, `Information Technology` |

**Response Shape** (`data` is an array):
```json
{
  "data": [
    {
      "ticker": "NVDA",
      "name": "Nvidia",
      "sector": "Information Technology",
      "industry": "Semiconductors",
      "mention_count": 1848
    }
  ],
  "meta": {
    "count": 503
  }
}
```

Sorted by `mention_count DESC`. Only companies with at least 1 mention are returned.

**Available Sectors**: Communication Services, Consumer Discretionary, Consumer Staples, Energy, Financials, Health Care, Industrials, Information Technology, Materials, Real Estate, Utilities.

**Performance**: **~60ms** local / **~277ms** production

---

### 5. GET /api/v1/companies/{ticker}

**Purpose**: Single company detail with mention stats and recent top articles.

**Path Parameters**:
- `ticker` (string, required) — S&P 500 ticker symbol (case-insensitive)

**Response Shape**:
```json
{
  "data": {
    "ticker": "AAPL",
    "name": "Apple Inc.",
    "sector": "Information Technology",
    "industry": "Technology Hardware, Storage & Peripherals",
    "cik": "0000320193",
    "mention_count": 1086,
    "recent_articles": [
      {
        "id": 12288631,
        "title": "UK regulator gets commitments from Apple...",
        "url": "https://...",
        "source": "Seeking Alpha (AAPL)",
        "published_at": "2026-02-10T07:09:09",
        "classified_at": "2026-02-10T21:17:38.335673"
      }
    ]
  }
}
```

`recent_articles` contains up to 10 FACTUAL centroid/noise articles from the last 7 days.

**Errors**: `404` if ticker not found.

**Performance**: **~22ms** local / **~135ms** production

---

### 6. GET /api/v1/stats

**Purpose**: System-wide statistics. Overview of database contents, classification, clustering, and entity mapping.

**Response Shape**:
```json
{
  "data": {
    "total_articles": 148564,
    "classification": {
      "classified": 112505,
      "factual": 52782,
      "opinion": 47316,
      "slop": 12407,
      "unclassified": 36059
    },
    "clustering": {
      "total_clusters": 9019,
      "clustered_articles": 39636
    },
    "entity_mapping": {
      "mapped_articles": 112505,
      "total_mentions": 70414
    },
    "ingestion": {
      "last_24h": 2196
    }
  }
}
```

**Invariants** (verified in tests):
- `classified + unclassified = total_articles`
- `factual + opinion + slop = classified`

**Performance**: **~295ms** local / **~502ms** production (runs 6 aggregate queries)

---

### 7. GET /api/v1/health

**Purpose**: Simple healthcheck for uptime monitoring.

**Response Shape**:
```json
{
  "data": {
    "status": "healthy",
    "database": "connected",
    "timestamp": "2026-02-11T02:11:21.296879Z"
  }
}
```

Returns `200` if healthy, `503` if database unreachable.

**Performance**: **~9ms** local / **~117ms** production

---

## Error Reference

| HTTP Status | Error Code | When |
|-------------|------------|------|
| 400 | `INVALID_PARAMETER` | Bad query param type, invalid timestamp, invalid UUID |
| 401 | `UNAUTHORIZED` | Missing, empty, or wrong API key |
| 404 | `NOT_FOUND` | Article, cluster, or company not found |
| 500 | `INTERNAL_ERROR` | Unhandled server error (no stack trace exposed) |
| 503 | `API_NOT_CONFIGURED` | Server has no API_V1_KEY set |

---

## Polling Strategy for Consumers

### Recommended: 5-minute polling cycle

```
every 5 minutes:
  response = GET /articles/feed?since=<last_cursor>&limit=100
  process(response.data)
  last_cursor = response.meta.latest_timestamp

  if response.meta.has_more:
    # More pages available — drain immediately
    while has_more:
      response = GET /articles/feed?since=<last_cursor>&limit=100
      process(response.data)
      last_cursor = response.meta.latest_timestamp
      has_more = response.meta.has_more
```

### Expected Volume Per Poll

| Metric | Value |
|--------|-------|
| Non-SEC articles ingested/day | ~1,360 |
| FACTUAL classification rate | ~47% (of classified) |
| Centroid + noise articles/day | ~450–600 |
| Articles per 5-min poll | **~2–4 articles** |
| Response size per poll | **~2–8 KB** |

At this volume, a 5-minute polling interval means each response typically contains just 2–4 new articles. The 100-article default limit provides a large buffer for catch-up after downtime.

### Catch-Up After Downtime

If the consumer is offline for hours/days, the cursor system handles it naturally:
- The `since` cursor remains where you left off
- Each call returns up to `limit` articles and advances the cursor
- Loop with `has_more` until caught up
- **Full backfill** (no `since` param, all ~53K FACTUAL articles) takes ~106 requests at limit=500, each taking ~63ms

---

## Rate & Capacity

| Metric | Value |
|--------|-------|
| Connection pool | 1–10 psycopg2 connections (shared with dashboard) |
| Flask concurrency | Single-threaded (Werkzeug dev server) |
| Max concurrent requests | ~10 (connection pool limit) |
| Database size | ~148K articles, growing ~1,360/day |
| Droplet specs | 2 CPU / 4 GB RAM |

### Current Architecture Limits

The API runs inside Flask's dev server (single-threaded). This is fine for 1–3 consumers polling every 5 minutes. For higher load:

1. **Add Gunicorn** (4 workers) — handles ~40 concurrent requests, trivial change to Dockerfile CMD
2. **Add Redis cache** for `/stats` endpoint (295ms is the slowest, but only changes hourly)
3. **Extract to separate container** if the dashboard and API compete for connections

### When You'd Need Webhooks

Webhooks (push instead of poll) would be warranted if:
- **Sub-minute freshness** — articles are classified hourly in batches, so real-time push doesn't improve on 5-min polling
- **Multiple consumers** — if 10+ consumers each poll every minute, that's load. Webhooks consolidate to 1 notification → N deliveries
- **Event-driven architecture** — if the consumer needs to trigger actions on new articles immediately

**For the current setup (1 consumer, 5-min polls, ~3 articles/poll), webhooks add complexity with no benefit.** The polling pattern is the right fit.

### When to Revisit

| Signal | Action |
|--------|--------|
| >5 consumers polling | Add Gunicorn workers or Redis caching |
| >100 req/min sustained | Extract API to separate container |
| Sub-30s freshness needed | Add webhook dispatcher to processing-worker |
| Full-text search needed | Add PostgreSQL `tsvector` column + `/search` endpoint |

---

## Latency Summary (All Endpoints)

### Local (Docker Desktop, Windows 11, 2 CPU)

| Endpoint | Avg | Min | Max |
|----------|-----|-----|-----|
| Feed (100 articles) | 20ms | 18ms | 21ms |
| Feed (500 articles) | 63ms | 62ms | 64ms |
| Feed + ticker filter | 24ms | 22ms | 26ms |
| Article detail | 12ms | 11ms | 13ms |
| Cluster detail | 10ms | 10ms | 11ms |
| Companies list | 63ms | 57ms | 70ms |
| Company detail | 22ms | 21ms | 24ms |
| Stats | 295ms | 283ms | 318ms |
| Health | 9ms | 9ms | 10ms |

### Production (DigitalOcean droplet, 2 CPU / 4 GB RAM)

Measured from external client. Includes ~100–200ms network round-trip.

| Endpoint | Avg | Min | Max |
|----------|-----|-----|-----|
| Feed (100 articles) | 222ms | 221ms | 222ms |
| Feed (500 articles) | 364ms | 363ms | 366ms |
| Feed + ticker filter | 202ms | 200ms | 205ms |
| Article detail | 116ms | 115ms | 117ms |
| Cluster detail | 117ms | 115ms | 119ms |
| Companies list | 277ms | 266ms | 284ms |
| Company detail | 135ms | 131ms | 138ms |
| Stats | 502ms | 493ms | 514ms |
| Health | 117ms | 115ms | 120ms |

All endpoints well under 1 second. Server-side processing times match local benchmarks — the difference is network latency. A consumer co-located with the droplet (or on nearby DigitalOcean infrastructure) would see local-tier response times.

### Test Results (37/38 passed)

Full test suite (`test_api_v1.py`) validated on both local and production: cursor pagination, ticker filtering, limit clamping, timestamp formats, ETag caching, auth rejection, cluster cross-checks, company filtering, stats invariants, and latency benchmarks.
