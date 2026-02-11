"""
REST API v1 for S&P 500 News Aggregation System.

Provides read-only access to deduplicated, classified, company-tagged
articles via timestamp-based cursor polling.

All endpoints require X-API-Key header authentication.
"""

import os
import hashlib
import logging
import traceback
import re
from datetime import datetime
from functools import wraps

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# Module-level reference, set by init_api_v1()
_db_manager = None


def init_api_v1(db_manager):
    """Initialize the API blueprint with a database manager reference."""
    global _db_manager
    _db_manager = db_manager


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def require_api_key(f):
    """Decorator that validates X-API-Key header against API_V1_KEY env var."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = os.environ.get('API_V1_KEY', '')
        if not api_key:
            return error_response('API_NOT_CONFIGURED',
                                  'API key not configured on server', 503)

        provided = request.headers.get('X-API-Key', '')
        if not provided or provided != api_key:
            return error_response('UNAUTHORIZED',
                                  'Invalid or missing API key', 401)

        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def success_response(data, meta=None):
    """Standard success envelope: {"data": ..., "meta": ...}"""
    body = {'data': data}
    if meta:
        body['meta'] = meta
    return jsonify(body)


def error_response(code, message, status=400):
    """Standard error envelope: {"error": {"code": ..., "message": ...}}"""
    return jsonify({'error': {'code': code, 'message': message}}), status


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def parse_iso_timestamp(value, param_name):
    """Parse an ISO 8601 timestamp string.
    Returns (datetime, None) on success or (None, error_response) on failure.
    """
    if not value:
        return None, None
    try:
        cleaned = value.replace('Z', '+00:00')
        return datetime.fromisoformat(cleaned), None
    except (ValueError, TypeError):
        return None, error_response(
            'INVALID_PARAMETER',
            f"'{param_name}' must be ISO 8601 format (e.g. 2026-02-10T18:30:00Z)")


_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)


def _is_valid_uuid(value):
    return bool(_UUID_RE.match(value))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@api_v1.route('/articles/feed')
@require_api_key
def articles_feed():
    """Core polling endpoint. Returns FACTUAL centroid + noise articles
    since a given timestamp, with cluster context and matched tickers.

    Query params:
        since  – ISO 8601 timestamp (exclusive lower bound on classified_at)
        ticker – Comma-separated tickers (e.g. "AAPL,MSFT")
        limit  – Max articles to return (default 100, max 500)
    """
    # -- Parse parameters --
    since_str = request.args.get('since', '')
    since_dt, err = parse_iso_timestamp(since_str, 'since')
    if err:
        return err

    ticker_param = request.args.get('ticker', '')
    tickers = ([t.strip().upper() for t in ticker_param.split(',') if t.strip()]
               if ticker_param else [])

    try:
        limit = min(max(int(request.args.get('limit', 100)), 1), 500)
    except (ValueError, TypeError):
        return error_response('INVALID_PARAMETER',
                              "'limit' must be an integer between 1 and 500")

    # -- Build query --
    params = []
    joins = []
    conditions = [
        "a.ready_for_kg = TRUE",
        "(a.is_cluster_centroid = TRUE OR a.cluster_label = -1)",
        "a.classified_at IS NOT NULL",
    ]

    if since_dt:
        conditions.append("a.classified_at > %s")
        params.append(since_dt)

    if tickers:
        joins.append(
            "JOIN article_company_mentions acm ON acm.article_id = a.id")
        placeholders = ','.join(['%s'] * len(tickers))
        conditions.append(f"acm.ticker IN ({placeholders})")
        params.extend(tickers)

    distinct = "DISTINCT " if tickers else ""
    join_clause = ' '.join(joins)
    where_clause = ' AND '.join(conditions)

    query = f"""
        SELECT {distinct}a.id, a.url, a.title, a.summary, a.source,
               a.published_at, a.fetched_at, a.classified_at,
               a.classification_label, a.classification_confidence,
               a.cluster_batch_id, a.cluster_label, a.is_cluster_centroid,
               a.distance_to_centroid
        FROM articles_raw a
        {join_clause}
        WHERE {where_clause}
        ORDER BY a.classified_at ASC, a.id ASC
        LIMIT %s
    """
    params.append(limit)

    try:
        with _db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                articles = cur.fetchall()

                if not articles:
                    return success_response([], meta={
                        'count': 0,
                        'latest_timestamp': None,
                        'has_more': False,
                    })

                article_ids = [row[0] for row in articles]

                # Batch fetch tickers
                cur.execute("""
                    SELECT article_id,
                           ARRAY_AGG(DISTINCT ticker ORDER BY ticker)
                    FROM article_company_mentions
                    WHERE article_id = ANY(%s)
                    GROUP BY article_id
                """, (article_ids,))
                ticker_map = {row[0]: row[1] for row in cur.fetchall()}

                # Batch fetch cluster sizes for non-noise articles
                cluster_keys = [
                    (str(row[10]), row[11])
                    for row in articles
                    if row[11] is not None and row[11] != -1
                      and row[10] is not None
                ]
                cluster_size_map = {}
                if cluster_keys:
                    unique_keys = list(set(cluster_keys))
                    ph = ', '.join(['(%s::uuid, %s)'] * len(unique_keys))
                    flat = [v for pair in unique_keys for v in pair]
                    cur.execute(f"""
                        SELECT cluster_batch_id::text, cluster_label,
                               COUNT(*) as size
                        FROM article_clusters
                        WHERE (cluster_batch_id, cluster_label)
                              IN ({ph})
                        GROUP BY cluster_batch_id, cluster_label
                    """, flat)
                    for row in cur.fetchall():
                        cluster_size_map[(row[0], row[1])] = row[2]

        # -- Build response --
        results = []
        for row in articles:
            aid = row[0]
            batch_id = str(row[10]) if row[10] else None
            label = row[11]
            cluster_size = (cluster_size_map.get((batch_id, label), 1)
                            if label is not None and label != -1 else 1)

            results.append({
                'id': aid,
                'url': row[1],
                'title': row[2],
                'summary': row[3] or '',
                'source': row[4],
                'published_at': row[5].isoformat() if row[5] else None,
                'fetched_at': row[6].isoformat() if row[6] else None,
                'classified_at': row[7].isoformat() if row[7] else None,
                'classification': {
                    'label': row[8],
                    'confidence': (round(float(row[9]), 4)
                                   if row[9] is not None else None),
                },
                'cluster': {
                    'batch_id': batch_id,
                    'label': label,
                    'is_centroid': row[12],
                    'cluster_size': cluster_size,
                },
                'tickers': ticker_map.get(aid, []),
            })

        latest_ts = results[-1]['classified_at'] if results else None
        has_more = len(results) == limit

        return success_response(results, meta={
            'count': len(results),
            'latest_timestamp': latest_ts,
            'has_more': has_more,
        })

    except Exception:
        logger.error("Feed endpoint error:\n%s", traceback.format_exc())
        return error_response('INTERNAL_ERROR',
                              'An unexpected error occurred', 500)


# ---------------------------------------------------------------------------

@api_v1.route('/articles/<int:article_id>')
@require_api_key
def article_detail(article_id):
    """Single article with full detail, classification, cluster info,
    and matched company tickers. Supports ETag caching."""

    try:
        with _db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.id, a.url, a.title, a.summary, a.source,
                           a.published_at, a.fetched_at, a.classified_at,
                           a.classification_label,
                           a.classification_confidence,
                           a.classification_source,
                           a.classification_model_version,
                           a.cluster_batch_id, a.cluster_label,
                           a.is_cluster_centroid, a.distance_to_centroid,
                           a.entity_mapped_at
                    FROM articles_raw a
                    WHERE a.id = %s
                """, (article_id,))
                row = cur.fetchone()

                if not row:
                    return error_response(
                        'NOT_FOUND',
                        f'Article {article_id} not found', 404)

                # Ticker mentions with match metadata
                cur.execute("""
                    SELECT acm.ticker, acm.mention_type, acm.match_method,
                           acm.confidence
                    FROM article_company_mentions acm
                    WHERE acm.article_id = %s
                    ORDER BY acm.confidence DESC
                """, (article_id,))
                mentions = [{
                    'ticker': m[0],
                    'mention_type': m[1],
                    'match_method': m[2],
                    'confidence': round(float(m[3]), 4),
                } for m in cur.fetchall()]

                # Cluster size
                batch_id = str(row[12]) if row[12] else None
                label = row[13]
                cluster_size = 1
                if label is not None and label != -1 and batch_id:
                    cur.execute("""
                        SELECT COUNT(*) FROM article_clusters
                        WHERE cluster_batch_id = %s
                          AND cluster_label = %s
                    """, (batch_id, label))
                    cluster_size = cur.fetchone()[0]

        # ETag
        etag_src = f"{row[0]}:{row[7]}:{row[12]}"
        etag = hashlib.md5(etag_src.encode()).hexdigest()

        if request.headers.get('If-None-Match') == etag:
            return '', 304

        data = {
            'id': row[0],
            'url': row[1],
            'title': row[2],
            'summary': row[3] or '',
            'source': row[4],
            'published_at': row[5].isoformat() if row[5] else None,
            'fetched_at': row[6].isoformat() if row[6] else None,
            'classified_at': row[7].isoformat() if row[7] else None,
            'classification': {
                'label': row[8],
                'confidence': (round(float(row[9]), 4)
                               if row[9] is not None else None),
                'source': row[10],
                'model_version': row[11],
            },
            'cluster': {
                'batch_id': batch_id,
                'label': label,
                'is_centroid': row[14],
                'distance_to_centroid': (round(float(row[15]), 4)
                                         if row[15] is not None else None),
                'cluster_size': cluster_size,
            },
            'entity_mapped_at': (row[16].isoformat()
                                 if row[16] else None),
            'company_mentions': mentions,
        }

        resp = jsonify({'data': data})
        resp.headers['ETag'] = etag
        return resp

    except Exception:
        logger.error("Article detail error:\n%s", traceback.format_exc())
        return error_response('INTERNAL_ERROR',
                              'An unexpected error occurred', 500)


# ---------------------------------------------------------------------------

@api_v1.route('/clusters/<batch_id>/<int:label>')
@require_api_key
def cluster_detail(batch_id, label):
    """All articles in a specific cluster with similarity scores."""

    if not _is_valid_uuid(batch_id):
        return error_response('INVALID_PARAMETER',
                              'batch_id must be a valid UUID')

    try:
        with _db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ac.article_id, a.title, a.url, a.source,
                           a.published_at, ac.is_centroid,
                           ac.distance_to_centroid,
                           COALESCE(1.0 - ac.distance_to_centroid, 1.0)
                               as similarity
                    FROM article_clusters ac
                    JOIN articles_raw a ON ac.article_id = a.id
                    WHERE ac.cluster_batch_id = %s
                      AND ac.cluster_label = %s
                    ORDER BY ac.distance_to_centroid ASC NULLS LAST
                """, (batch_id, label))
                rows = cur.fetchall()

                if not rows:
                    return error_response(
                        'NOT_FOUND',
                        f'Cluster {batch_id}/{label} not found', 404)

                article_ids = [r[0] for r in rows]

                # Batch fetch tickers
                cur.execute("""
                    SELECT article_id,
                           ARRAY_AGG(DISTINCT ticker ORDER BY ticker)
                    FROM article_company_mentions
                    WHERE article_id = ANY(%s)
                    GROUP BY article_id
                """, (article_ids,))
                ticker_map = {r[0]: r[1] for r in cur.fetchall()}

        articles = []
        for r in rows:
            articles.append({
                'id': r[0],
                'title': r[1],
                'url': r[2],
                'source': r[3],
                'published_at': r[4].isoformat() if r[4] else None,
                'is_centroid': r[5],
                'distance_to_centroid': (round(float(r[6]), 4)
                                         if r[6] is not None else None),
                'similarity': round(float(r[7]), 4),
                'tickers': ticker_map.get(r[0], []),
            })

        return success_response({
            'batch_id': batch_id,
            'label': label,
            'size': len(articles),
            'articles': articles,
        })

    except Exception:
        logger.error("Cluster detail error:\n%s", traceback.format_exc())
        return error_response('INTERNAL_ERROR',
                              'An unexpected error occurred', 500)


# ---------------------------------------------------------------------------

@api_v1.route('/companies')
@require_api_key
def companies_list():
    """S&P 500 companies with article mention counts.
    Optional ?sector=Technology filter."""

    sector = request.args.get('sector', '').strip()

    try:
        with _db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                params = []
                where = ""
                if sector:
                    where = "WHERE c.sector = %s"
                    params.append(sector)

                cur.execute(f"""
                    SELECT c.ticker, c.name, c.sector, c.industry,
                           COUNT(acm.id) as mention_count
                    FROM companies c
                    JOIN article_company_mentions acm
                         ON acm.company_id = c.id
                    {where}
                    GROUP BY c.id, c.ticker, c.name, c.sector, c.industry
                    HAVING COUNT(acm.id) > 0
                    ORDER BY mention_count DESC
                """, params)
                rows = cur.fetchall()

        companies = [{
            'ticker': r[0],
            'name': r[1],
            'sector': r[2],
            'industry': r[3],
            'mention_count': r[4],
        } for r in rows]

        return success_response(companies, meta={'count': len(companies)})

    except Exception:
        logger.error("Companies list error:\n%s", traceback.format_exc())
        return error_response('INTERNAL_ERROR',
                              'An unexpected error occurred', 500)


# ---------------------------------------------------------------------------

@api_v1.route('/companies/<ticker>')
@require_api_key
def company_detail(ticker):
    """Single company detail with mention stats and recent top articles."""

    ticker = ticker.strip().upper()

    try:
        with _db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # Company info + total mentions
                cur.execute("""
                    SELECT c.id, c.ticker, c.name, c.sector, c.industry,
                           c.cik, COUNT(acm.id) as mention_count
                    FROM companies c
                    LEFT JOIN article_company_mentions acm
                              ON acm.company_id = c.id
                    WHERE c.ticker = %s
                    GROUP BY c.id
                """, (ticker,))
                company = cur.fetchone()

                if not company:
                    return error_response(
                        'NOT_FOUND',
                        f'Company {ticker} not found', 404)

                # Recent FACTUAL centroid articles (last 7 days)
                cur.execute("""
                    SELECT a.id, a.title, a.url, a.source,
                           a.published_at, a.classified_at
                    FROM articles_raw a
                    JOIN article_company_mentions acm
                         ON acm.article_id = a.id
                    JOIN companies c ON c.id = acm.company_id
                    WHERE c.ticker = %s
                      AND a.ready_for_kg = TRUE
                      AND (a.is_cluster_centroid = TRUE
                           OR a.cluster_label = -1)
                      AND a.published_at >= NOW() - INTERVAL '7 days'
                    ORDER BY a.published_at DESC
                    LIMIT 10
                """, (ticker,))
                recent = cur.fetchall()

        recent_articles = [{
            'id': r[0],
            'title': r[1],
            'url': r[2],
            'source': r[3],
            'published_at': r[4].isoformat() if r[4] else None,
            'classified_at': r[5].isoformat() if r[5] else None,
        } for r in recent]

        return success_response({
            'ticker': company[1],
            'name': company[2],
            'sector': company[3],
            'industry': company[4],
            'cik': company[5],
            'mention_count': company[6],
            'recent_articles': recent_articles,
        })

    except Exception:
        logger.error("Company detail error:\n%s", traceback.format_exc())
        return error_response('INTERNAL_ERROR',
                              'An unexpected error occurred', 500)


# ---------------------------------------------------------------------------

@api_v1.route('/stats')
@require_api_key
def system_stats():
    """System statistics: articles, classification, clusters, entity mapping."""

    try:
        with _db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # Total articles
                cur.execute("SELECT COUNT(*) FROM articles_raw")
                total_articles = cur.fetchone()[0]

                # Classification breakdown
                cur.execute("""
                    SELECT classification_label, COUNT(*)
                    FROM articles_raw
                    WHERE classification_label IS NOT NULL
                    GROUP BY classification_label
                """)
                class_rows = cur.fetchall()
                classification = {r[0]: r[1] for r in class_rows}
                classified_total = sum(classification.values())

                # Cluster stats
                cur.execute("""
                    SELECT COUNT(DISTINCT (cluster_batch_id, cluster_label)),
                           COUNT(*)
                    FROM article_clusters
                    WHERE cluster_label != -1
                """)
                cluster_row = cur.fetchone()
                total_clusters = cluster_row[0]
                clustered_articles = cluster_row[1]

                # Entity mapping coverage
                cur.execute("""
                    SELECT COUNT(*) FROM articles_raw
                    WHERE entity_mapped_at IS NOT NULL
                """)
                mapped_articles = cur.fetchone()[0]

                cur.execute(
                    "SELECT COUNT(*) FROM article_company_mentions")
                total_mentions = cur.fetchone()[0]

                # Recent ingestion (last 24h)
                cur.execute("""
                    SELECT COUNT(*) FROM articles_raw
                    WHERE fetched_at >= NOW() - INTERVAL '24 hours'
                """)
                recent_24h = cur.fetchone()[0]

        return success_response({
            'total_articles': total_articles,
            'classification': {
                'classified': classified_total,
                'factual': classification.get('FACTUAL', 0),
                'opinion': classification.get('OPINION', 0),
                'slop': classification.get('SLOP', 0),
                'unclassified': total_articles - classified_total,
            },
            'clustering': {
                'total_clusters': total_clusters,
                'clustered_articles': clustered_articles,
            },
            'entity_mapping': {
                'mapped_articles': mapped_articles,
                'total_mentions': total_mentions,
            },
            'ingestion': {
                'last_24h': recent_24h,
            },
        })

    except Exception:
        logger.error("Stats error:\n%s", traceback.format_exc())
        return error_response('INTERNAL_ERROR',
                              'An unexpected error occurred', 500)


# ---------------------------------------------------------------------------

@api_v1.route('/health')
@require_api_key
def health():
    """Simplified healthcheck — database connectivity + timestamp."""

    db_ok = False
    try:
        with _db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                db_ok = cur.fetchone()[0] == 1
    except Exception:
        db_ok = False

    status = 'healthy' if db_ok else 'unhealthy'
    http_status = 200 if db_ok else 503

    resp = success_response({
        'status': status,
        'database': 'connected' if db_ok else 'disconnected',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
    })
    return resp, http_status


# ---------------------------------------------------------------------------
# Blueprint error handler — catch-all, no stack traces exposed
# ---------------------------------------------------------------------------

@api_v1.app_errorhandler(404)
def handle_404(e):
    """Only fires for /api/v1/ routes that don't match any endpoint."""
    if request.path.startswith('/api/v1/'):
        return error_response('NOT_FOUND', 'Endpoint not found', 404)
    # Let the main app handle non-v1 404s
    return e
