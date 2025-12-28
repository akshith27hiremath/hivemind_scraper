#!/usr/bin/env python3
"""Sandbox web app for live teacher labeling preview.

This Flask app shows random articles one-by-one and labels them live
using the teacher API (Anthropic or OpenAI). Use this to validate
the teacher prompt and labeling quality before running full batch.

Usage:
    # Start sandbox with Anthropic (default)
    python sandbox_labeler.py

    # Use OpenAI instead
    python sandbox_labeler.py --provider openai

    # Custom port
    python sandbox_labeler.py --port 5001

Then visit: http://localhost:5050
"""

import os
import sys
import argparse
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request
import random
import importlib

# Load .env from parent directory BEFORE importing other modules
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# CRITICAL: Override POSTGRES_HOST to localhost when running outside Docker
# The .env has 'postgres' which is the Docker network hostname
os.environ['POSTGRES_HOST'] = 'localhost'

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.teacher_student import TeacherLabeler
from logger import setup_logger

logger = setup_logger(__name__)

# Global state
db = None
labeler = None
article_pool = []
custom_prompt = None  # If set, overrides labeler's prompt

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Classification Sandbox</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            max-width: 1000px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0 0 10px 0;
        }
        .stats {
            font-size: 14px;
            opacity: 0.9;
        }
        .article-card {
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .source-badge {
            display: inline-block;
            padding: 5px 10px;
            background: #e3f2fd;
            color: #1976d2;
            border-radius: 5px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 15px;
        }
        .headline {
            font-size: 20px;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
            line-height: 1.4;
        }
        .summary {
            color: #666;
            line-height: 1.6;
            margin-bottom: 20px;
        }
        .result {
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
        }
        .result.FACTUAL {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
        }
        .result.OPINION {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
        }
        .result.SLOP {
            background: #ffebee;
            border-left: 4px solid #f44336;
        }
        .result-header {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 10px;
        }
        .result.FACTUAL .result-header { color: #2e7d32; }
        .result.OPINION .result-header { color: #ef6c00; }
        .result.SLOP .result-header { color: #c62828; }
        .confidence {
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }
        .reasoning {
            font-style: italic;
            color: #555;
            margin-top: 10px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            transition: background 0.3s;
        }
        .button:hover {
            background: #5568d3;
        }
        .button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .button-group {
            text-align: center;
            margin-top: 20px;
        }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 6px;
            margin-top: 20px;
        }
        .prompt-editor {
            background: #fff;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .prompt-editor h3 {
            margin-top: 0;
            cursor: pointer;
            user-select: none;
        }
        .prompt-editor h3:hover {
            color: #667eea;
        }
        .prompt-content {
            margin-top: 15px;
        }
        .prompt-content textarea {
            width: 100%;
            height: 400px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .prompt-status {
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 14px;
        }
        .prompt-status.custom {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
        }
        .prompt-status.default {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
        }
        .button-group-prompt {
            margin-top: 10px;
        }
        .button-group-prompt button {
            margin-right: 10px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔬 Classification Sandbox</h1>
        <div class="stats">
            <strong>{{ provider }}</strong> / {{ model }}
            | Pool: <span id="pool-size">{{ pool_size }}</span> articles (excluding SEC EDGAR)
        </div>
    </div>

    <div id="article-container"></div>

    <div class="button-group">
        <button class="button" onclick="loadNext()" id="next-button">
            Get Next Article
        </button>
    </div>

    <div class="prompt-editor">
        <h3 onclick="togglePromptEditor()">📝 Prompt Editor (click to toggle)</h3>
        <div id="prompt-editor-status" class="prompt-status default">
            Using <strong>default</strong> prompt
        </div>
        <div id="prompt-content" class="prompt-content" style="display: none;">
            <textarea id="prompt-textarea">{{ default_prompt }}</textarea>
            <div class="button-group-prompt">
                <button class="button" onclick="savePrompt()">Save & Use This Prompt</button>
                <button class="button" onclick="resetPrompt()" style="background: #f44336;">Reset to Default</button>
            </div>
        </div>
    </div>

    <div class="article-card" style="margin-top: 30px; background: #f8f9fa;">
        <h3 style="margin-top: 0;">🧪 Test Custom Input</h3>
        <div style="margin-bottom: 15px;">
            <label style="display: block; font-weight: 600; margin-bottom: 5px;">
                Headline:
            </label>
            <input type="text" id="custom-headline"
                   placeholder="Enter a headline to classify..."
                   style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">
        </div>
        <div style="margin-bottom: 15px;">
            <label style="display: block; font-weight: 600; margin-bottom: 5px;">
                Summary (optional):
            </label>
            <textarea id="custom-summary"
                      placeholder="Enter article summary/description..."
                      rows="3"
                      style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; font-family: inherit;"></textarea>
        </div>
        <button class="button" onclick="classifyCustom()" id="custom-button">
            Classify Custom Input
        </button>
    </div>

    <script>
        let loading = false;

        async function loadNext() {
            if (loading) return;
            loading = true;

            const button = document.getElementById('next-button');
            button.disabled = true;
            button.textContent = 'Loading...';

            const container = document.getElementById('article-container');
            container.innerHTML = '<div class="loading"><div class="spinner"></div>Classifying article...</div>';

            try {
                const response = await fetch('/api/classify-next');
                const data = await response.json();

                if (data.error) {
                    container.innerHTML = `<div class="error">${data.error}</div>`;
                } else {
                    renderArticle(data);
                    document.getElementById('pool-size').textContent = data.remaining;
                }
            } catch (error) {
                container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
            } finally {
                loading = false;
                button.disabled = false;
                button.textContent = 'Get Next Article';
            }
        }

        function renderArticle(data) {
            const container = document.getElementById('article-container');
            const summary = data.summary ? `<div class="summary">${escapeHtml(data.summary)}</div>` : '';

            container.innerHTML = `
                <div class="article-card">
                    <div class="source-badge">${escapeHtml(data.source)}</div>
                    <div class="headline">${escapeHtml(data.headline)}</div>
                    ${summary}

                    <div class="result ${data.classification}">
                        <div class="result-header">
                            ${getEmoji(data.classification)} ${data.classification}
                        </div>
                        <div class="confidence">
                            Confidence: ${(data.confidence * 100).toFixed(0)}%
                        </div>
                        <div class="reasoning">
                            "${escapeHtml(data.reasoning)}"
                        </div>
                    </div>
                </div>
            `;
        }

        function getEmoji(classification) {
            const emojis = {
                'FACTUAL': '✅',
                'OPINION': '💭',
                'SLOP': '🗑️'
            };
            return emojis[classification] || '❓';
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function classifyCustom() {
            const headline = document.getElementById('custom-headline').value.trim();
            const summary = document.getElementById('custom-summary').value.trim();

            if (!headline) {
                alert('Please enter a headline');
                return;
            }

            const button = document.getElementById('custom-button');
            button.disabled = true;
            button.textContent = 'Classifying...';

            const container = document.getElementById('article-container');
            container.innerHTML = '<div class="loading"><div class="spinner"></div>Classifying your input...</div>';

            try {
                const response = await fetch('/api/classify-custom', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({headline, summary})
                });
                const data = await response.json();

                if (data.error) {
                    container.innerHTML = `<div class="error">${data.error}</div>`;
                } else {
                    renderArticle(data);
                }
            } catch (error) {
                container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
            } finally {
                button.disabled = false;
                button.textContent = 'Classify Custom Input';
            }
        }

        function togglePromptEditor() {
            const content = document.getElementById('prompt-content');
            content.style.display = content.style.display === 'none' ? 'block' : 'none';
        }

        async function savePrompt() {
            const prompt = document.getElementById('prompt-textarea').value;
            try {
                const response = await fetch('/api/set-prompt', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({prompt})
                });
                const data = await response.json();
                if (data.success) {
                    const status = document.getElementById('prompt-editor-status');
                    status.className = 'prompt-status custom';
                    status.innerHTML = 'Using <strong>custom</strong> prompt';
                    alert('Prompt saved! All classifications will now use your custom prompt.');
                }
            } catch (error) {
                alert('Error saving prompt: ' + error.message);
            }
        }

        async function resetPrompt() {
            try {
                const response = await fetch('/api/reset-prompt', {method: 'POST'});
                const data = await response.json();
                if (data.success) {
                    document.getElementById('prompt-textarea').value = data.prompt;
                    const status = document.getElementById('prompt-editor-status');
                    status.className = 'prompt-status default';
                    status.innerHTML = 'Using <strong>default</strong> prompt';
                    alert('Prompt reset to default!');
                }
            } catch (error) {
                alert('Error resetting prompt: ' + error.message);
            }
        }

        // Allow Enter key to submit custom input
        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById('custom-headline').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') classifyCustom();
            });
        });

        // Load first article on page load
        window.onload = () => loadNext();
    </script>
</body>
</html>
'''


def init_app(provider='anthropic', model=None):
    """Initialize database and labeler."""
    global db, labeler, article_pool

    db = ProcessingDatabaseManager()
    labeler = TeacherLabeler(provider=provider, model=model, rate_limit_delay=0.1)

    # Load article pool (excluding SEC EDGAR)
    logger.info("Loading article pool...")
    article_pool = db.get_unlabeled_articles_sample(limit=500, stratify_by_source=True)
    random.shuffle(article_pool)

    logger.info(f"Loaded {len(article_pool)} articles")


app = Flask(__name__)


@app.route('/')
def index():
    """Render sandbox UI."""
    return render_template_string(
        HTML_TEMPLATE,
        provider=labeler.provider.upper(),
        model=labeler.model,
        pool_size=len(article_pool),
        default_prompt=labeler.PROMPT_TEMPLATE
    )


@app.route('/api/classify-next')
def classify_next():
    """Classify next random article."""
    try:
        # HOT-RELOAD: Reload prompt from file on each request
        global labeler
        from mechanical_refinery import teacher_student
        importlib.reload(teacher_student.teacher_labeler)
        from mechanical_refinery.teacher_student import TeacherLabeler
        labeler.PROMPT_TEMPLATE = TeacherLabeler.PROMPT_TEMPLATE

        if not article_pool:
            return jsonify({'error': 'No more articles in pool. Refresh page to reload.'})

        # Pop random article
        article = article_pool.pop(random.randrange(len(article_pool)))

        # Classify with teacher
        result = labeler.label_single(article)

        return jsonify({
            'article_id': article['id'],
            'headline': article['title'],
            'summary': article.get('summary'),
            'source': article['source'],
            'classification': result.label,
            'confidence': result.confidence,
            'reasoning': result.reasoning,
            'remaining': len(article_pool)
        })

    except Exception as e:
        logger.error(f"Classification error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/classify-custom', methods=['POST'])
def classify_custom():
    """Classify custom user input."""
    try:
        # HOT-RELOAD: Reload prompt from file on each request
        global labeler
        from mechanical_refinery import teacher_student
        importlib.reload(teacher_student.teacher_labeler)
        from mechanical_refinery.teacher_student import TeacherLabeler
        labeler.PROMPT_TEMPLATE = TeacherLabeler.PROMPT_TEMPLATE

        data = request.get_json()
        headline = data.get('headline', '').strip()
        summary = data.get('summary', '').strip()

        if not headline:
            return jsonify({'error': 'Headline is required'}), 400

        # Create article dict for classification
        article = {
            'id': 0,
            'title': headline,
            'summary': summary if summary else None
        }

        # Use custom prompt if set
        if custom_prompt:
            _classify_with_custom_prompt(article)

        # Classify with teacher
        result = labeler.label_single(article)

        return jsonify({
            'article_id': 0,
            'headline': headline,
            'summary': summary if summary else None,
            'source': 'Custom Input',
            'classification': result.label,
            'confidence': result.confidence,
            'reasoning': result.reasoning,
            'remaining': len(article_pool)
        })

    except Exception as e:
        logger.error(f"Custom classification error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/set-prompt', methods=['POST'])
def set_prompt():
    """Set custom prompt."""
    global custom_prompt
    try:
        data = request.get_json()
        prompt = data.get('prompt', '').strip()

        if not prompt:
            return jsonify({'error': 'Prompt cannot be empty'}), 400

        # Update labeler's prompt template
        labeler.PROMPT_TEMPLATE = prompt
        custom_prompt = prompt

        logger.info("Custom prompt activated")
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error setting prompt: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset-prompt', methods=['POST'])
def reset_prompt():
    """Reset to default prompt."""
    global custom_prompt
    try:
        # Reimport to get original
        from mechanical_refinery.teacher_student import TeacherLabeler
        default_prompt = TeacherLabeler.PROMPT_TEMPLATE

        labeler.PROMPT_TEMPLATE = default_prompt
        custom_prompt = None

        logger.info("Prompt reset to default")
        return jsonify({'success': True, 'prompt': default_prompt})

    except Exception as e:
        logger.error(f"Error resetting prompt: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def _classify_with_custom_prompt(article):
    """Helper to apply custom prompt (called before labeler.label_single)."""
    # The prompt is already updated in labeler.PROMPT_TEMPLATE
    pass


def main():
    parser = argparse.ArgumentParser(description='Sandbox labeler web app')
    parser.add_argument('--provider', type=str, default='anthropic',
                        choices=['openai', 'anthropic'],
                        help='API provider (default: anthropic)')
    parser.add_argument('--model', type=str, default=None,
                        help='Model name (optional)')
    parser.add_argument('--port', type=int, default=5050,
                        help='Port to run on (default: 5050)')

    args = parser.parse_args()

    print("=" * 80)
    print("CLASSIFICATION SANDBOX")
    print("=" * 80)
    print()
    print(f"Provider: {args.provider.upper()}")
    if args.model:
        print(f"Model: {args.model}")
    print()
    print("Initializing...")

    # Initialize
    init_app(provider=args.provider, model=args.model)

    print()
    print("=" * 80)
    print(f">>> Sandbox running at: http://localhost:{args.port}")
    print("=" * 80)
    print()
    print("Press Ctrl+C to stop")
    print()

    # Run Flask
    app.run(host='0.0.0.0', port=args.port, debug=False)


if __name__ == '__main__':
    main()
