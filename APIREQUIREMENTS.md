# REST API Requirements

**Last Updated**: 2026-02-10
**Status**: Planning
**Related**: `TECH-STACK.md`, `CLAUDE.md`

---

## Context

The scraperMVP system ingests ~2,700 S&P 500 news articles/day, classifies them (FACTUAL/OPINION/SLOP via DistilBERT at 86.5% accuracy), and clusters duplicates using sentence embeddings. A downstream consumer application needs to poll for deduplicated, classified articles via a REST API.

Currently, the only external access is either direct DB connection (insecure, exposed on port 5432) or the internal web dashboard (no auth, not designed for machine consumption). The REST API replaces both as the proper interface.

---

## Consumer Profile

- **Type**: Single application (initially), more consumers possible later
- **Access pattern**: Polls every 5 minutes for new articles
- **Data needed**: Deduplicated FACTUAL articles (cluster centroids), eventually filtered by company/ticker
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
- **Future**: Will support `?ticker=AAPL` filter once article-company mapping (ticker column) is implemented via NLP. Design the endpoint so this filter can be added without breaking changes.

**Noise articles** (cluster_label=-1, unique articles with no duplicates) should also be returned - they are valid unique stories, not errors.

---

## Secondary Endpoints

### `GET /api/v1/articles/{id}`
Single article with full detail (title, summary, source, classification, cluster info).

### `GET /api/v1/clusters/{batch_id}/{label}`
All articles in a specific cluster. Allows consumer to see what was deduplicated.

### `GET /api/v1/stats`
System statistics: total articles, classification breakdown, cluster counts, ingestion rates.

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

### Pending (Do Not Block API on These)
- **Ticker/company mapping**: NLP-based entity extraction to add `ticker` column to `articles_raw`. Separate planning task. API should be designed to accept `?ticker=` filter once available.
- **Article-company junction table**: Alternative to ticker column for articles mentioning multiple companies.

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
