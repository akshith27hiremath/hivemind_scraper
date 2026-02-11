#!/usr/bin/env python3
"""
Simple Web Dashboard for S&P 500 News Aggregator
Provides article browsing, filtering, and API health monitoring
"""

from flask import Flask, render_template, request, jsonify
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

# Add parent directory to path to import from ingestion-worker
sys.path.insert(0, '/app/ingestion-worker')

from src.database import DatabaseManager
from src.config import Config
from src.api_clients import FinnhubClient, AlphaVantageClient
from src.parsers.sec_parser import SECParser

app = Flask(__name__)
db_manager = DatabaseManager()

# Register REST API v1 Blueprint
from api_v1 import api_v1, init_api_v1
init_api_v1(db_manager)
app.register_blueprint(api_v1)


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@app.route('/api/articles')
def get_articles():
    """
    Get articles with optional filters.

    Query params:
        source: Filter by source name
        keyword: Search in title/summary
        days: Articles from last N days
        limit: Number of articles (default: 50)
        offset: Pagination offset (default: 0)
        ticker: Comma-separated tickers to filter by (e.g. "AAPL,MSFT")
    """
    source = request.args.get('source', '')
    keyword = request.args.get('keyword', '')
    days = request.args.get('days', type=int)
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    ticker = request.args.get('ticker', '')

    params = []
    joins = []
    conditions = ["1=1"]

    if ticker:
        tickers = [t.strip().upper() for t in ticker.split(',') if t.strip()]
        if tickers:
            joins.append("JOIN article_company_mentions acm ON acm.article_id = a.id")
            placeholders = ','.join(['%s'] * len(tickers))
            conditions.append(f"acm.ticker IN ({placeholders})")
            params.extend(tickers)

    if source and source != 'all':
        conditions.append("a.source = %s")
        params.append(source)

    if keyword:
        conditions.append("(a.title ILIKE %s OR a.summary ILIKE %s)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if days:
        conditions.append("a.fetched_at >= %s")
        cutoff_date = datetime.now() - timedelta(days=days)
        params.append(cutoff_date)

    join_clause = ' '.join(joins)
    where_clause = ' AND '.join(conditions)

    # Use DISTINCT when joining to avoid duplicates (article mentions multiple tickers)
    distinct = "DISTINCT " if ticker else ""

    full_query = f"""
        SELECT {distinct}a.id, a.url, a.title, a.summary, a.source, a.published_at, a.fetched_at, a.classification_label
        FROM articles_raw a
        {join_clause}
        WHERE {where_clause}
        ORDER BY a.published_at DESC NULLS LAST, a.fetched_at DESC
        LIMIT {limit} OFFSET {offset}
    """

    count_query = f"""
        SELECT COUNT({distinct}a.id)
        FROM articles_raw a
        {join_clause}
        WHERE {where_clause}
    """

    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(full_query, params)
            articles = cur.fetchall()

            cur.execute(count_query, params)
            total = cur.fetchone()[0]

            # Batch fetch tickers for returned articles
            article_ids = [a[0] for a in articles]
            article_tickers = {}
            if article_ids:
                cur.execute("""
                    SELECT article_id, ARRAY_AGG(DISTINCT ticker ORDER BY ticker)
                    FROM article_company_mentions
                    WHERE article_id = ANY(%s)
                    GROUP BY article_id
                """, (article_ids,))
                for row in cur.fetchall():
                    article_tickers[row[0]] = row[1]

    # Format results
    results = []
    for article in articles:
        results.append({
            'url': article[1],
            'title': article[2],
            'summary': article[3] or '',
            'source': article[4],
            'published_at': article[5].isoformat() if article[5] else None,
            'fetched_at': article[6].isoformat() if article[6] else None,
            'classification_label': article[7] if len(article) > 7 else None,
            'tickers': article_tickers.get(article[0], []),
        })

    return jsonify({
        'articles': results,
        'total': total,
        'limit': limit,
        'offset': offset
    })


@app.route('/api/sources')
def get_sources():
    """Get list of all sources with article counts."""
    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, COUNT(*) as count
                FROM articles_raw
                GROUP BY source
                ORDER BY count DESC
            """)
            results = cur.fetchall()

    sources = [{'name': row[0], 'count': row[1]} for row in results]
    return jsonify({'sources': sources})


@app.route('/api/stats')
def get_stats():
    """Get database statistics."""
    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            # Total articles
            cur.execute("SELECT COUNT(*) FROM articles_raw")
            total = cur.fetchone()[0]

            # Recent activity (last 24h)
            cur.execute("""
                SELECT COUNT(*) FROM articles_raw
                WHERE fetched_at >= NOW() - INTERVAL '24 hours'
            """)
            recent = cur.fetchone()[0]

            # Date range
            cur.execute("""
                SELECT MIN(published_at), MAX(published_at)
                FROM articles_raw
            """)
            oldest, newest = cur.fetchone()

            # Unique sources
            cur.execute("SELECT COUNT(DISTINCT source) FROM articles_raw")
            sources = cur.fetchone()[0]

    return jsonify({
        'total_articles': total,
        'recent_24h': recent,
        'oldest_article': oldest.isoformat() if oldest else None,
        'newest_article': newest.isoformat() if newest else None,
        'unique_sources': sources
    })


@app.route('/api/clusters')
def get_clusters():
    """
    Get paginated cluster results, optionally filtered by recency and similarity.

    Query params:
        hours: Only show clusters created within the last N hours (default: 24).
               Use 0 or omit for all time.
        page: Page number (default: 1)
        per_page: Clusters per page (default: 20, max: 100)
        min_similarity: Minimum avg similarity 0.0-1.0 (default: 0.5)
        max_similarity: Maximum avg similarity 0.0-1.0 (default: 1.0)

    Returns paginated clusters with their articles, sorted by similarity.
    """
    hours = request.args.get('hours', 24, type=int)
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))
    min_similarity = request.args.get('min_similarity', 0.5, type=float)
    max_similarity = request.args.get('max_similarity', 1.0, type=float)
    offset = (page - 1) * per_page

    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            # Build optional time filter on article_clusters.created_at
            time_filter = ""
            params = []
            if hours and hours > 0:
                time_filter = "AND ac.created_at >= NOW() - INTERVAL '%s hours'"
                params = [hours]

            # Base CTE for cluster aggregation
            base_cte = """
                WITH cluster_info AS (
                    SELECT
                        ac.cluster_batch_id,
                        ac.cluster_label,
                        COUNT(*) as size,
                        AVG(COALESCE(1.0 - ac.distance_to_centroid, 1.0)) as avg_similarity
                    FROM article_clusters ac
                    WHERE ac.clustering_method = 'embeddings'
                        AND ac.cluster_label <> -1
                        {time_filter}
                    GROUP BY ac.cluster_batch_id, ac.cluster_label
                    HAVING COUNT(*) >= 2
                ),
                filtered AS (
                    SELECT * FROM cluster_info
                    WHERE avg_similarity < 0.999
                        AND avg_similarity >= %s
                        AND avg_similarity <= %s
                )
            """.format(time_filter=time_filter)

            sim_params = params + [min_similarity, max_similarity]

            # Get total count and aggregate stats
            count_query = base_cte + """
                SELECT COUNT(*),
                       COALESCE(SUM(size), 0),
                       COALESCE(AVG(size), 0)
                FROM filtered
            """
            cur.execute(count_query, sim_params)
            total_clusters, total_articles, avg_size = cur.fetchone()
            total_clusters = int(total_clusters)
            total_articles = int(total_articles)

            # Get paginated cluster IDs
            page_query = base_cte + """
                SELECT cluster_batch_id, cluster_label
                FROM filtered
                ORDER BY avg_similarity DESC, size DESC
                LIMIT %s OFFSET %s
            """
            cur.execute(page_query, sim_params + [per_page, offset])
            page_keys = cur.fetchall()

            if not page_keys:
                return jsonify({
                    'clusters': [],
                    'total_clusters': total_clusters,
                    'total_articles': total_articles,
                    'avg_size': round(float(avg_size), 1),
                    'page': page,
                    'per_page': per_page,
                    'total_pages': 0
                })

            # Fetch full article data only for this page's clusters
            key_pairs = [(str(k[0]), k[1]) for k in page_keys]
            placeholders = ', '.join(['(%s, %s)'] * len(key_pairs))
            flat_keys = [v for pair in key_pairs for v in pair]

            detail_query = """
                SELECT
                    ac.cluster_batch_id,
                    ac.cluster_label,
                    a.title,
                    a.url,
                    a.source,
                    ac.is_centroid,
                    a.published_at,
                    COALESCE(1.0 - ac.distance_to_centroid, 1.0) as similarity
                FROM article_clusters ac
                JOIN articles_raw a ON ac.article_id = a.id
                WHERE (ac.cluster_batch_id, ac.cluster_label) IN ({placeholders})
                ORDER BY ac.cluster_batch_id, ac.cluster_label, ac.distance_to_centroid ASC NULLS LAST
            """.format(placeholders=placeholders)

            cur.execute(detail_query, flat_keys)
            rows = cur.fetchall()

    # Group rows into clusters, preserving page order
    from collections import OrderedDict
    cluster_map = OrderedDict()
    for batch_id, label in page_keys:
        cluster_map[(str(batch_id), label)] = {
            'articles': [],
            'similarities': []
        }

    for row in rows:
        batch_id, label, title, url, source, is_centroid, published_at, similarity = row
        key = (str(batch_id), label)
        if key in cluster_map:
            cluster_map[key]['articles'].append({
                'title': title,
                'url': url,
                'source': source,
                'is_centroid': is_centroid,
                'published_at': published_at.isoformat() if published_at else None,
                'similarity': round(float(similarity), 3)
            })
            cluster_map[key]['similarities'].append(float(similarity))

    formatted_clusters = []
    for (batch_id, label), data in cluster_map.items():
        avg_sim = sum(data['similarities']) / len(data['similarities']) if data['similarities'] else 0
        formatted_clusters.append({
            'batch_id': batch_id,
            'cluster_label': label,
            'size': len(data['articles']),
            'avg_similarity': round(avg_sim, 3),
            'articles': data['articles']
        })

    total_pages = (total_clusters + per_page - 1) // per_page

    return jsonify({
        'clusters': formatted_clusters,
        'total_clusters': total_clusters,
        'total_articles': total_articles,
        'avg_size': round(float(avg_size), 1),
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages
    })


@app.route('/api/source-breakdown')
def get_source_breakdown():
    """
    Get source breakdown for pie charts.

    Returns total and daily (last 24h) article counts by source.
    Combines SEC sources and Seeking Alpha ticker-specific sources.
    """
    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            # Total breakdown with source aggregation
            cur.execute("""
                SELECT
                    CASE
                        WHEN source LIKE 'SEC EDGAR%' THEN 'SEC EDGAR (All Filings)'
                        WHEN source LIKE 'Seeking Alpha (%' THEN 'Seeking Alpha'
                        WHEN source LIKE 'Finnhub (SeekingAlpha)%' THEN 'Seeking Alpha'
                        ELSE source
                    END as grouped_source,
                    COUNT(*) as count
                FROM articles_raw
                GROUP BY grouped_source
                ORDER BY count DESC
            """)
            total_results = cur.fetchall()

            # Daily breakdown (last 24 hours) with same aggregation
            cur.execute("""
                SELECT
                    CASE
                        WHEN source LIKE 'SEC EDGAR%' THEN 'SEC EDGAR (All Filings)'
                        WHEN source LIKE 'Seeking Alpha (%' THEN 'Seeking Alpha'
                        WHEN source LIKE 'Finnhub (SeekingAlpha)%' THEN 'Seeking Alpha'
                        ELSE source
                    END as grouped_source,
                    COUNT(*) as count
                FROM articles_raw
                WHERE published_at >= NOW() - INTERVAL '24 hours'
                GROUP BY grouped_source
                ORDER BY count DESC
            """)
            daily_results = cur.fetchall()

    total_breakdown = [{'source': row[0], 'count': row[1]} for row in total_results]
    daily_breakdown = [{'source': row[0], 'count': row[1]} for row in daily_results]

    return jsonify({
        'total': total_breakdown,
        'daily': daily_breakdown
    })


@app.route('/api/health')
def health_check():
    """
    Check health of all data sources and APIs.

    Returns status for:
    - Database connection
    - Finnhub API
    - Alpha Vantage API
    - SEC EDGAR
    - RSS Feeds (sample check)
    """
    health_status = {
        'timestamp': datetime.now().isoformat(),
        'services': {}
    }

    # 1. Database
    try:
        if db_manager.test_connection():
            health_status['services']['database'] = {
                'status': 'healthy',
                'message': 'Connection successful',
                'last_check': datetime.now().isoformat()
            }
        else:
            health_status['services']['database'] = {
                'status': 'unhealthy',
                'message': 'Connection failed',
                'last_check': datetime.now().isoformat()
            }
    except Exception as e:
        health_status['services']['database'] = {
            'status': 'error',
            'message': str(e),
            'last_check': datetime.now().isoformat()
        }

    # 2. Finnhub API
    if Config.FINNHUB_API_KEY:
        try:
            finnhub = FinnhubClient(Config.FINNHUB_API_KEY)
            test_articles = finnhub.fetch_company_news('AAPL', days_back=1)

            health_status['services']['finnhub'] = {
                'status': 'healthy',
                'message': f'Fetched {len(test_articles)} test articles',
                'api_key_configured': True,
                'rate_limit_status': 'ok',
                'last_check': datetime.now().isoformat()
            }
        except Exception as e:
            error_msg = str(e)
            status = 'rate_limited' if '429' in error_msg or 'limit' in error_msg.lower() else 'error'

            health_status['services']['finnhub'] = {
                'status': status,
                'message': error_msg,
                'api_key_configured': True,
                'last_check': datetime.now().isoformat()
            }
    else:
        health_status['services']['finnhub'] = {
            'status': 'unconfigured',
            'message': 'API key not configured',
            'api_key_configured': False
        }

    # 3. Alpha Vantage API
    if Config.ALPHAVANTAGE_API_KEY:
        try:
            av = AlphaVantageClient(Config.ALPHAVANTAGE_API_KEY)
            test_articles = av.fetch_news_sentiment('MSFT', limit=5)

            health_status['services']['alpha_vantage'] = {
                'status': 'healthy',
                'message': f'Fetched {len(test_articles)} test articles',
                'api_key_configured': True,
                'rate_limit_status': 'ok',
                'last_check': datetime.now().isoformat()
            }
        except Exception as e:
            error_msg = str(e)
            status = 'rate_limited' if '429' in error_msg or 'limit' in error_msg.lower() else 'error'

            health_status['services']['alpha_vantage'] = {
                'status': status,
                'message': error_msg,
                'api_key_configured': True,
                'last_check': datetime.now().isoformat()
            }
    else:
        health_status['services']['alpha_vantage'] = {
            'status': 'unconfigured',
            'message': 'API key not configured',
            'api_key_configured': False
        }

    # 4. SEC EDGAR
    try:
        sec = SECParser()
        tickers_with_cik = db_manager.get_tickers_with_cik(limit=1)

        if tickers_with_cik:
            ticker, cik = tickers_with_cik[0]
            test_filings = sec.fetch_company_filings(cik, ticker)

            health_status['services']['sec_edgar'] = {
                'status': 'healthy',
                'message': f'Fetched {len(test_filings)} test filings',
                'last_check': datetime.now().isoformat()
            }
        else:
            health_status['services']['sec_edgar'] = {
                'status': 'warning',
                'message': 'No CIK values in database',
                'last_check': datetime.now().isoformat()
            }
    except Exception as e:
        health_status['services']['sec_edgar'] = {
            'status': 'error',
            'message': str(e),
            'last_check': datetime.now().isoformat()
        }

    # 5. RSS Feeds (check recent activity)
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # Check if RSS feeds have fetched articles recently (last 60 min)
                cur.execute("""
                    SELECT source, COUNT(*) as count, MAX(fetched_at) as last_fetch
                    FROM articles_raw
                    WHERE source IN (
                        'Reuters Business', 'Yahoo Finance', 'MarketWatch', 'Seeking Alpha',
                        'Investing.com', 'CNBC', 'Benzinga', 'TechCrunch',
                        'The Verge', 'Bloomberg'
                    )
                    GROUP BY source
                    HAVING MAX(fetched_at) >= NOW() - INTERVAL '60 minutes'
                """)
                active_feeds = cur.fetchall()

                # Total RSS sources configured
                total_rss = 10
                active_count = len(active_feeds)

                if active_count >= 7:  # At least 70% working
                    health_status['services']['rss_feeds'] = {
                        'status': 'healthy',
                        'message': f'{active_count}/{total_rss} feeds active in last 60 min',
                        'active_feeds': active_count,
                        'total_feeds': total_rss,
                        'last_check': datetime.now().isoformat()
                    }
                elif active_count >= 4:
                    health_status['services']['rss_feeds'] = {
                        'status': 'degraded',
                        'message': f'Only {active_count}/{total_rss} feeds active',
                        'active_feeds': active_count,
                        'total_feeds': total_rss,
                        'last_check': datetime.now().isoformat()
                    }
                else:
                    health_status['services']['rss_feeds'] = {
                        'status': 'unhealthy',
                        'message': f'Only {active_count}/{total_rss} feeds active',
                        'active_feeds': active_count,
                        'total_feeds': total_rss,
                        'last_check': datetime.now().isoformat()
                    }
    except Exception as e:
        health_status['services']['rss_feeds'] = {
            'status': 'error',
            'message': str(e),
            'last_check': datetime.now().isoformat()
        }

    # Overall health
    statuses = [svc['status'] for svc in health_status['services'].values()]
    if all(s == 'healthy' for s in statuses):
        health_status['overall'] = 'healthy'
    elif any(s in ['error', 'unhealthy'] for s in statuses):
        health_status['overall'] = 'degraded'
    else:
        health_status['overall'] = 'warning'

    return jsonify(health_status)


@app.route('/api/companies')
def get_companies():
    """
    Get companies that have at least 1 article mention, sorted by mention count.
    Used to populate the company filter dropdown.
    """
    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.ticker, c.name, c.sector, COUNT(acm.id) as mention_count
                FROM companies c
                JOIN article_company_mentions acm ON acm.company_id = c.id
                GROUP BY c.id, c.ticker, c.name, c.sector
                HAVING COUNT(acm.id) > 0
                ORDER BY mention_count DESC
            """)
            results = cur.fetchall()

    companies = [
        {'ticker': r[0], 'name': r[1], 'sector': r[2], 'mention_count': r[3]}
        for r in results
    ]
    return jsonify({'companies': companies})


@app.route('/api/company-stats')
def get_company_stats():
    """
    Get top 25 most-mentioned companies with stats.
    Used for the analytics section.

    Query params:
        days: Time window in days (default: 30). Use 0 for all time.
    """
    days = request.args.get('days', 30, type=int)

    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            params = []
            time_filter = ""
            if days > 0:
                time_filter = "WHERE acm.created_at >= NOW() - INTERVAL '%s days'"
                params = [days]

            cur.execute(f"""
                SELECT c.ticker, c.name, c.sector, COUNT(acm.id) as mention_count
                FROM article_company_mentions acm
                JOIN companies c ON c.id = acm.company_id
                {time_filter}
                GROUP BY c.id, c.ticker, c.name, c.sector
                ORDER BY mention_count DESC
                LIMIT 25
            """, params)
            results = cur.fetchall()

    companies = [
        {'ticker': r[0], 'name': r[1], 'sector': r[2], 'mentions': r[3]}
        for r in results
    ]
    return jsonify({'companies': companies})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
