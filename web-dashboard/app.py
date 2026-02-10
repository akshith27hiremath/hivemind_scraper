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
    """
    source = request.args.get('source', '')
    keyword = request.args.get('keyword', '')
    days = request.args.get('days', type=int)
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    # Build query
    query = """
        SELECT url, title, summary, source, published_at, fetched_at, classification_label
        FROM articles_raw
        WHERE 1=1
    """
    params = []

    if source and source != 'all':
        query += " AND source = %s"
        params.append(source)

    if keyword:
        query += " AND (title ILIKE %s OR summary ILIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if days:
        query += " AND fetched_at >= %s"
        cutoff_date = datetime.now() - timedelta(days=days)
        params.append(cutoff_date)

    query += " ORDER BY published_at DESC NULLS LAST, fetched_at DESC"
    query += f" LIMIT {limit} OFFSET {offset}"

    # Get total count for pagination
    count_query = query.split('ORDER BY')[0].replace(
        'SELECT url, title, summary, source, published_at, fetched_at, classification_label',
        'SELECT COUNT(*)'
    )

    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            # Get articles
            cur.execute(query, params)
            articles = cur.fetchall()

            # Get total count
            cur.execute(count_query, params)
            total = cur.fetchone()[0]

    # Format results
    results = []
    for article in articles:
        results.append({
            'url': article[0],
            'title': article[1],
            'summary': article[2] or '',
            'source': article[3],
            'published_at': article[4].isoformat() if article[4] else None,
            'fetched_at': article[5].isoformat() if article[5] else None,
            'classification_label': article[6] if len(article) > 6 else None,
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
    Get cluster results, optionally filtered by recency.

    Query params:
        hours: Only show clusters created within the last N hours (default: 24).
               Use 0 or omit for all time.

    Returns clusters with their articles, sorted by similarity.
    """
    hours = request.args.get('hours', 24, type=int)

    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            # Build optional time filter on article_clusters.created_at
            time_filter = ""
            params = []
            if hours and hours > 0:
                time_filter = "AND ac.created_at >= NOW() - INTERVAL '%s hours'"
                params = [hours]

            # Get cluster data with correlation scores
            # Note: distance_to_centroid is stored as (1 - similarity), so similarity = 1 - distance
            query = """
                WITH cluster_info AS (
                    SELECT
                        ac.cluster_batch_id,
                        ac.cluster_label,
                        COUNT(*) as size,
                        ARRAY_AGG(a.title ORDER BY ac.distance_to_centroid ASC NULLS LAST) as titles,
                        ARRAY_AGG(a.url ORDER BY ac.distance_to_centroid ASC NULLS LAST) as urls,
                        ARRAY_AGG(a.source ORDER BY ac.distance_to_centroid ASC NULLS LAST) as sources,
                        ARRAY_AGG(ac.is_centroid ORDER BY ac.distance_to_centroid ASC NULLS LAST) as centroids,
                        ARRAY_AGG(a.published_at ORDER BY ac.distance_to_centroid ASC NULLS LAST) as published_dates,
                        ARRAY_AGG(COALESCE(1.0 - ac.distance_to_centroid, 1.0) ORDER BY ac.distance_to_centroid ASC NULLS LAST) as similarities,
                        AVG(COALESCE(1.0 - ac.distance_to_centroid, 1.0)) as avg_similarity
                    FROM article_clusters ac
                    JOIN articles_raw a ON ac.article_id = a.id
                    WHERE ac.clustering_method = 'embeddings'
                        AND ac.cluster_label <> -1
                        {time_filter}
                    GROUP BY ac.cluster_batch_id, ac.cluster_label
                    HAVING COUNT(*) >= 2
                )
                SELECT * FROM cluster_info
                WHERE avg_similarity < 0.999
                ORDER BY avg_similarity DESC, size DESC
            """.format(time_filter=time_filter)

            cur.execute(query, params)

            clusters = cur.fetchall()

    # Format clusters
    formatted_clusters = []
    for cluster in clusters:
        batch_id, label, size, titles, urls, sources, centroids, dates, similarities, avg_similarity = cluster

        articles = []
        for i in range(len(titles)):
            articles.append({
                'title': titles[i],
                'url': urls[i],
                'source': sources[i],
                'is_centroid': centroids[i],
                'published_at': dates[i].isoformat() if dates[i] else None,
                'similarity': round(float(similarities[i]), 3)
            })

        formatted_clusters.append({
            'batch_id': str(batch_id),
            'cluster_label': label,
            'size': size,
            'avg_similarity': round(float(avg_similarity), 3),
            'articles': articles
        })

    return jsonify({
        'clusters': formatted_clusters,
        'total_clusters': len(formatted_clusters)
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
