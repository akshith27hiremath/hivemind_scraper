# REST API Requirements

**Last Updated**: 2026-02-11
**Status**: Planning
**Related**: `TECH-STACK.md`, `CLAUDE.md`

---

## Context

The scraperMVP system ingests ~1,360 non-SEC S&P 500 news articles/day, classifies them (FACTUAL/OPINION/SLOP via DistilBERT at 86.5% accuracy), clusters duplicates using sentence embeddings, and maps articles to S&P 500 companies via regex entity matching (70K+ mentions across 503 companies). A downstream consumer application needs to poll for deduplicated, classified, company-tagged articles via a REST API.

Currently, the only external access is either direct DB connection (insecure, exposed on port 5432) or the internal web dashboard (no auth, not designed for machine consumption). The REST API replaces both as the proper interface.

---

## Consumer Profile

- **Type**: Single application (initially), more consumers possible later
- **Access pattern**: Polls every 5 minutes for new articles
- **Data needed**: Deduplicated FACTUAL articles (cluster centroids), filtered by company/ticker
- **Access level**: Read-only
- **Latency tolerance**: Seconds (not real-time, polling-based)

---

## Primary Endpoint

### `GET /api/v1/articles/feed?since=<ISO timestamp>`

The core polling endpoint. Returns new FACTUAL centroid articles since the given timestamp.

**Requirements**:
- Returns articles where `ready_for_kg=TRUE` and `is_cluster_centroid=TRUE`
- Ordered by `published_at DESC` or `classified_at DESC`
- Includes cluster context: how many related articles exist in the cluster
- Supports `since` parameter (ISO 8601 timestamp) to fetch only new articles since last poll
- Must use cursor-based or timestamp-based pagination (NOT OFFSET - degrades at scale)
- Response includes a `latest_timestamp` field so the consumer knows what to pass next
- Supports `?ticker=AAPL` filter via `article_company_mentions` junction table (entity mapping deployed, 70K+ mentions). Multiple tickers supported: `?ticker=AAPL,MSFT`
- Each article in the response includes its matched company tickers (from `article_company_mentions`)

**Noise articles** (cluster_label=-1, unique articles with no duplicates) should also be returned - they are valid unique stories, not errors.

---

## Secondary Endpoints

### `GET /api/v1/articles/{id}`
Single article with full detail (title, summary, source, classification, cluster info, matched company tickers).

### `GET /api/v1/clusters/{batch_id}/{label}`
All articles in a specific cluster. Allows consumer to see what was deduplicated.

### `GET /api/v1/companies`
List of S&P 500 companies with article mention counts. Useful for consumers to discover which tickers are available for filtering. Supports optional `?sector=Technology` filter.

### `GET /api/v1/companies/{ticker}`
Single company detail with recent mention stats and top articles.

### `GET /api/v1/stats`
System statistics: total articles, classification breakdown, cluster counts, entity mapping coverage, ingestion rates.

### `GET /api/v1/health`
Simple healthcheck for monitoring. Database connectivity, service status.

---

## Authentication

- **Mechanism**: API key via `X-API-Key` header
- **Storage**: API keys stored server-side (environment variable or DB table)
- **Scope**: All `/api/v1/` endpoints require valid key
- **Rate limiting**: Optional but recommended (consumer polls every 5 min, so low volume)

---

## Security Requirements

1. **Close port 5432** on the droplet firewall after API is deployed. No more direct DB access from outside.
2. API key authentication on all endpoints.
3. Input validation on all query parameters (since, limit, etc.).
4. No debug mode in production.
5. No exposure of internal schema or stack traces in error responses.

---

## Performance Requirements

- **Feed endpoint latency**: <500ms for typical polling query (last 5 minutes of articles)
- **Pagination**: Cursor-based (not OFFSET). The `since` timestamp naturally serves as cursor for the feed endpoint.
- **Caching**: ETag / If-Modified-Since headers for article detail endpoints. Articles don't change after classification/clustering.
- **Connection pooling**: Must use connection pool (not per-request connections).
- **Future optimization hooks**:
  - Materialized view for cluster data (expensive JOIN currently runs per-request)
  - Redis cache layer if multiple consumers or higher polling frequency needed
  - Response field selection (`?fields=slim` vs `?fields=full`) to reduce payload size

---

## Response Format

Standard JSON envelope:

```json
{
  "data": [...],
  "meta": {
    "count": 42,
    "latest_timestamp": "2026-02-10T18:30:00Z",
    "has_more": false
  }
}
```

Error responses:

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "Human-readable description"
  }
}
```

---

## Deployment Strategy

**Option A (recommended for now)**: Add `/api/v1/` as a Flask Blueprint inside the existing `web-dashboard` service. No new container needed on the 4GB droplet.

**Option B (future)**: Extract to standalone API service when load justifies it. Blueprint structure makes this a clean split.

The existing dashboard routes (`/api/articles`, `/api/clusters`, etc.) remain untouched for the web UI. The new `/api/v1/` namespace is separate.

---

## Data Dependencies

### Available Now
- Deduplicated FACTUAL articles (centroids) via `ready_for_kg=TRUE` + `is_cluster_centroid=TRUE`
- Cluster metadata (batch_id, label, distance, size)
- Classification metadata (label, confidence, model version)
- All article fields (title, summary, source, url, timestamps)
- **Entity mapping** via `article_company_mentions` junction table (70K+ rows, 503 companies)
  - Links articles to S&P 500 companies (ticker, mention_type, match_method, confidence)
  - 45.5% of articles match at least one company
  - Tracking column `entity_mapped_at` on `articles_raw`
  - Indexed on `article_id`, `company_id`, `ticker`
- **Companies** table with 503 S&P 500 constituents (ticker, name, sector, industry, CIK)

---

## Versioning

- All endpoints under `/api/v1/` prefix
- Breaking changes require `/api/v2/` (new namespace, old one kept alive)
- Non-breaking additions (new response fields, new optional query params) are fine within v1

---

## What the API Does NOT Do

- No write operations (read-only)
- No user management or OAuth (single API key is sufficient)
- No WebSocket/SSE streaming (polling is the access pattern)
- No full-text search (consumer queries by timestamp, not keyword)
- No aggregation/analytics endpoints beyond basic stats (that's the dashboard's job)
