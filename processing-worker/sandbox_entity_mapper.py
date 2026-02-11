#!/usr/bin/env python3
"""
Sandbox web app for testing entity mapping interactively.

Shows random articles and displays which S&P 500 companies the mapper
detects. Useful for validating matching quality, tuning aliases, and
spot-checking results before running the full backfill.

Usage:
    set POSTGRES_HOST=localhost
    python sandbox_entity_mapper.py

Then visit: http://localhost:5051
"""

import os
import sys
import argparse
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request
import random

# Load .env from parent directory
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

os.environ.setdefault('POSTGRES_HOST', 'localhost')

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.entity_mapper import CompanyEntityMapper, AMBIGUOUS_TICKERS
from logger import setup_logger

logger = setup_logger(__name__)

# Global state
db = None
mapper = None
article_pool = []

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Entity Mapping Sandbox</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            max-width: 1100px;
            margin: 40px auto;
            padding: 20px;
            background: #0d1117;
            color: #e6edf3;
        }
        .header {
            background: linear-gradient(135deg, #238636 0%, #1f6feb 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        .header h1 { margin: 0 0 10px 0; }
        .stats {
            font-size: 14px;
            opacity: 0.9;
        }
        .article-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
        }
        .source-badge {
            display: inline-block;
            padding: 4px 10px;
            background: rgba(56, 139, 253, 0.15);
            color: #58a6ff;
            border: 1px solid rgba(56, 139, 253, 0.3);
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 12px;
        }
        .headline {
            font-size: 20px;
            font-weight: 600;
            color: #e6edf3;
            margin-bottom: 10px;
            line-height: 1.4;
        }
        .summary {
            color: #8b949e;
            line-height: 1.6;
            margin-bottom: 15px;
        }
        .mentions-container {
            margin-top: 20px;
        }
        .mentions-header {
            font-size: 16px;
            font-weight: 600;
            color: #e6edf3;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .mention-count {
            background: rgba(63, 185, 80, 0.15);
            color: #3fb950;
            border: 1px solid rgba(63, 185, 80, 0.3);
            border-radius: 20px;
            padding: 2px 10px;
            font-size: 13px;
        }
        .mention-card {
            background: #0d1117;
            border: 1px solid #21262d;
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .mention-card:hover {
            border-color: #388bfd;
        }
        .ticker-badge {
            display: inline-block;
            padding: 3px 10px;
            background: rgba(63, 185, 80, 0.15);
            color: #3fb950;
            border: 1px solid rgba(63, 185, 80, 0.3);
            border-radius: 4px;
            font-size: 13px;
            font-weight: 700;
            font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
            margin-right: 10px;
        }
        .mention-info {
            display: flex;
            align-items: center;
            gap: 10px;
            flex: 1;
        }
        .mention-details {
            font-size: 13px;
            color: #8b949e;
        }
        .mention-meta {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .meta-badge {
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: 'JetBrains Mono', monospace;
        }
        .meta-badge.method-name { background: rgba(56, 139, 253, 0.15); color: #58a6ff; }
        .meta-badge.method-alias { background: rgba(163, 113, 247, 0.15); color: #a371f7; }
        .meta-badge.method-ticker { background: rgba(210, 153, 34, 0.15); color: #d29922; }
        .meta-badge.method-brand { background: rgba(219, 109, 40, 0.15); color: #db6d28; }
        .meta-badge.type-title { background: rgba(63, 185, 80, 0.15); color: #3fb950; }
        .meta-badge.type-summary { background: rgba(139, 148, 158, 0.15); color: #8b949e; }
        .meta-badge.type-both { background: rgba(56, 139, 253, 0.15); color: #58a6ff; }
        .confidence-bar {
            width: 60px;
            height: 6px;
            background: #21262d;
            border-radius: 3px;
            overflow: hidden;
        }
        .confidence-fill {
            height: 100%;
            border-radius: 3px;
        }
        .no-mentions {
            text-align: center;
            padding: 30px;
            color: #6e7681;
            font-style: italic;
        }
        .button {
            background: #238636;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 15px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .button:hover { background: #2ea043; }
        .button:disabled { background: #21262d; color: #484f58; cursor: not-allowed; }
        .button.secondary {
            background: #21262d;
            border: 1px solid #30363d;
            color: #c9d1d9;
        }
        .button.secondary:hover {
            background: #30363d;
        }
        .button-group {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin-top: 20px;
        }
        .custom-input {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 25px;
            margin-top: 20px;
        }
        .custom-input h3 { margin-top: 0; color: #e6edf3; }
        .custom-input input, .custom-input textarea {
            width: 100%;
            padding: 10px 14px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #e6edf3;
            font-size: 14px;
            margin-bottom: 10px;
        }
        .custom-input input:focus, .custom-input textarea:focus {
            border-color: #388bfd;
            outline: none;
            box-shadow: 0 0 0 3px rgba(56, 139, 253, 0.15);
        }
        .custom-input textarea {
            height: 80px;
            resize: vertical;
            font-family: inherit;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #8b949e;
        }
        .spinner {
            border: 3px solid #30363d;
            border-top: 3px solid #238636;
            border-radius: 50%;
            width: 36px;
            height: 36px;
            animation: spin 0.8s linear infinite;
            margin: 15px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .highlight {
            background: rgba(210, 153, 34, 0.2);
            border-radius: 2px;
            padding: 0 2px;
        }
        .mapper-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }
        .mapper-stat {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .mapper-stat-value {
            font-size: 24px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #58a6ff;
        }
        .mapper-stat-label {
            font-size: 12px;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 4px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Entity Mapping Sandbox</h1>
        <div class="stats">
            {{ num_companies }} companies | {{ num_patterns }} patterns | {{ num_ambiguous }} ambiguous tickers
            | Pool: <span id="pool-size">{{ pool_size }}</span> articles
        </div>
    </div>

    <div class="mapper-stats">
        <div class="mapper-stat">
            <div class="mapper-stat-value">{{ num_companies }}</div>
            <div class="mapper-stat-label">Companies</div>
        </div>
        <div class="mapper-stat">
            <div class="mapper-stat-value">{{ num_patterns }}</div>
            <div class="mapper-stat-label">Regex Patterns</div>
        </div>
        <div class="mapper-stat">
            <div class="mapper-stat-value">{{ num_aliases }}</div>
            <div class="mapper-stat-label">Aliases Loaded</div>
        </div>
    </div>

    <div class="button-group">
        <button class="button" onclick="loadRandom()" id="random-button">
            Get Random Article
        </button>
        <button class="button secondary" onclick="loadRandomSA()">
            Get SA (ticker) Article
        </button>
    </div>

    <div id="article-container">
        <div class="loading">Click "Get Random Article" to start testing.</div>
    </div>

    <div class="custom-input">
        <h3>Test Custom Input</h3>
        <input type="text" id="custom-headline" placeholder="Enter a headline...">
        <textarea id="custom-summary" placeholder="Enter a summary (optional)..."></textarea>
        <button class="button" onclick="testCustom()">Test Entity Mapping</button>
    </div>

    <script>
        function loadRandom() {
            document.getElementById('article-container').innerHTML = `
                <div class="loading"><div class="spinner"></div>Loading article...</div>
            `;
            fetch('/api/random')
                .then(res => res.json())
                .then(renderResult)
                .catch(err => {
                    document.getElementById('article-container').innerHTML = `
                        <div class="article-card" style="color: #f85149;">Error: ${err.message}</div>
                    `;
                });
        }

        function loadRandomSA() {
            document.getElementById('article-container').innerHTML = `
                <div class="loading"><div class="spinner"></div>Loading SA article...</div>
            `;
            fetch('/api/random-sa')
                .then(res => res.json())
                .then(renderResult)
                .catch(err => {
                    document.getElementById('article-container').innerHTML = `
                        <div class="article-card" style="color: #f85149;">Error: ${err.message}</div>
                    `;
                });
        }

        function testCustom() {
            const headline = document.getElementById('custom-headline').value;
            const summary = document.getElementById('custom-summary').value;
            if (!headline) { alert('Enter a headline'); return; }

            document.getElementById('article-container').innerHTML = `
                <div class="loading"><div class="spinner"></div>Mapping entities...</div>
            `;

            fetch('/api/test-custom', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({headline, summary})
            })
            .then(res => res.json())
            .then(renderResult)
            .catch(err => {
                document.getElementById('article-container').innerHTML = `
                    <div class="article-card" style="color: #f85149;">Error: ${err.message}</div>
                `;
            });
        }

        function renderResult(data) {
            const container = document.getElementById('article-container');
            const mentions = data.mentions || [];

            // Highlight matched text in title and summary
            let highlightedTitle = escapeHtml(data.title);
            let highlightedSummary = escapeHtml(data.summary || '');

            mentions.forEach(m => {
                const escapedMatch = escapeHtml(m.matched_text);
                const regex = new RegExp('\\\\b' + escapeRegex(escapedMatch) + '\\\\b', 'gi');
                highlightedTitle = highlightedTitle.replace(regex, `<span class="highlight">${escapedMatch}</span>`);
                if (highlightedSummary) {
                    highlightedSummary = highlightedSummary.replace(regex, `<span class="highlight">${escapedMatch}</span>`);
                }
            });

            let mentionsHtml = '';
            if (mentions.length > 0) {
                mentionsHtml = mentions.map(m => {
                    const confPct = (m.confidence * 100).toFixed(0);
                    const confColor = m.confidence >= 0.95 ? '#3fb950' :
                                      m.confidence >= 0.85 ? '#58a6ff' :
                                      m.confidence >= 0.8 ? '#d29922' : '#f85149';
                    return `
                        <div class="mention-card">
                            <div class="mention-info">
                                <span class="ticker-badge">${m.ticker}</span>
                                <span class="mention-details">
                                    matched "<strong>${escapeHtml(m.matched_text)}</strong>"
                                </span>
                            </div>
                            <div class="mention-meta">
                                <span class="meta-badge method-${m.match_method}">${m.match_method}</span>
                                <span class="meta-badge type-${m.mention_type}">${m.mention_type}</span>
                                <div style="text-align:right; min-width:50px;">
                                    <div style="font-size:11px; font-family:monospace; color:${confColor};">${confPct}%</div>
                                    <div class="confidence-bar">
                                        <div class="confidence-fill" style="width:${confPct}%; background:${confColor};"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                mentionsHtml = '<div class="no-mentions">No companies detected in this article.</div>';
            }

            // SA ticker validation
            let saValidation = '';
            if (data.sa_ticker) {
                const saMatch = mentions.some(m => m.ticker === data.sa_ticker);
                saValidation = `
                    <div style="margin-top:12px; padding:10px; border-radius:6px;
                                background: ${saMatch ? 'rgba(63,185,80,0.1)' : 'rgba(248,81,73,0.1)'};
                                border: 1px solid ${saMatch ? 'rgba(63,185,80,0.3)' : 'rgba(248,81,73,0.3)'};
                                font-size:13px;">
                        SA source ticker: <strong>${data.sa_ticker}</strong>
                        ${saMatch ? '&check; Found in mentions' : '&cross; NOT found in mentions'}
                    </div>
                `;
            }

            container.innerHTML = `
                <div class="article-card">
                    <span class="source-badge">${escapeHtml(data.source || 'Custom Input')}</span>
                    ${data.article_id ? '<span style="font-size:12px; color:#6e7681; margin-left:8px;">ID: ' + data.article_id + '</span>' : ''}
                    <div class="headline">${highlightedTitle}</div>
                    ${highlightedSummary ? '<div class="summary">' + highlightedSummary + '</div>' : ''}
                    ${saValidation}
                    <div class="mentions-container">
                        <div class="mentions-header">
                            Detected Companies
                            <span class="mention-count">${mentions.length} ${mentions.length === 1 ? 'match' : 'matches'}</span>
                        </div>
                        ${mentionsHtml}
                    </div>
                </div>
            `;
        }

        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        function escapeRegex(str) {
            return str.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
        }
    </script>
</body>
</html>
'''

app = Flask(__name__)


@app.route('/')
def index():
    from mechanical_refinery.company_aliases import COMPANY_ALIASES
    return render_template_string(
        HTML_TEMPLATE,
        num_companies=len(mapper.ticker_to_id),
        num_patterns=len(mapper.patterns),
        num_aliases=len(COMPANY_ALIASES),
        num_ambiguous=len(AMBIGUOUS_TICKERS),
        pool_size=len(article_pool),
    )


@app.route('/api/random')
def random_article():
    if not article_pool:
        return jsonify({'error': 'No articles in pool'}), 404

    article = random.choice(article_pool)
    return _map_and_respond(article)


@app.route('/api/random-sa')
def random_sa_article():
    """Get a random Seeking Alpha article (has ticker in source)."""
    sa_articles = [a for a in article_pool if 'Seeking Alpha (' in (a.get('source') or '')]
    if not sa_articles:
        return jsonify({'error': 'No Seeking Alpha ticker articles in pool'}), 404

    article = random.choice(sa_articles)
    return _map_and_respond(article)


@app.route('/api/test-custom', methods=['POST'])
def test_custom():
    data = request.get_json()
    headline = data.get('headline', '')
    summary = data.get('summary', '')

    article = {
        'id': 0,
        'title': headline,
        'summary': summary,
        'source': 'Custom Input',
    }
    return _map_and_respond(article)


def _map_and_respond(article):
    """Map an article and return JSON response."""
    mentions = mapper.map_article(article)

    # Extract SA ticker if present
    sa_ticker = None
    source = article.get('source') or ''
    if 'Seeking Alpha (' in source:
        try:
            sa_ticker = source.split('(')[1].split(')')[0]
        except (IndexError, AttributeError):
            pass

    return jsonify({
        'article_id': article.get('id'),
        'title': article.get('title', ''),
        'summary': article.get('summary', ''),
        'source': source,
        'sa_ticker': sa_ticker,
        'mentions': [
            {
                'ticker': m.ticker,
                'mention_type': m.mention_type,
                'match_method': m.match_method,
                'matched_text': m.matched_text,
                'confidence': m.confidence,
            }
            for m in sorted(mentions, key=lambda x: -x.confidence)
        ]
    })


def main():
    global db, mapper, article_pool

    parser = argparse.ArgumentParser(description='Entity mapping sandbox')
    parser.add_argument('--port', type=int, default=5051, help='Port (default: 5051)')
    parser.add_argument('--pool-size', type=int, default=5000,
                        help='Number of articles to load into pool (default: 5000)')
    args = parser.parse_args()

    print("Loading database and mapper...")

    db = ProcessingDatabaseManager()

    companies = db.get_companies_lookup()
    print(f"  Loaded {len(companies)} companies")

    mapper = CompanyEntityMapper(companies)
    print(f"  Compiled {len(mapper.patterns)} regex patterns")

    # Load article pool
    print(f"  Loading {args.pool_size} articles for testing pool...")
    with db.get_connection() as conn:
        from psycopg2.extras import RealDictCursor
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, title, summary, source
                FROM articles_raw
                WHERE source NOT LIKE 'SEC EDGAR%%'
                ORDER BY RANDOM()
                LIMIT %s
            """, (args.pool_size,))
            article_pool = [dict(row) for row in cur.fetchall()]

    print(f"  Pool loaded: {len(article_pool)} articles")

    sa_count = sum(1 for a in article_pool if 'Seeking Alpha (' in (a.get('source') or ''))
    print(f"  SA ticker articles in pool: {sa_count}")

    print(f"\nStarting sandbox at http://localhost:{args.port}")
    app.run(host='0.0.0.0', port=args.port, debug=True)


if __name__ == '__main__':
    main()
