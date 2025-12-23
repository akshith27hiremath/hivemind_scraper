"""
Embeddings Sandbox - Test headline similarity with sentence transformers.

A mini web app to test how the embeddings clustering works on headlines.
"""

import os
import sys
from flask import Flask, render_template, request, jsonify
import numpy as np

# Add processing-worker to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'processing-worker'))

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

# Load model once at startup
print("Loading sentence transformer model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded!")

# Store headlines in memory for the session
stored_headlines = []
stored_embeddings = None


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    """Analyze headlines for similarity."""
    global stored_headlines, stored_embeddings

    data = request.json
    headlines = data.get('headlines', [])
    threshold = float(data.get('threshold', 0.78))

    if not headlines:
        return jsonify({'error': 'No headlines provided'}), 400

    # Filter empty headlines
    headlines = [h.strip() for h in headlines if h.strip()]

    if len(headlines) < 2:
        return jsonify({'error': 'Need at least 2 headlines to compare'}), 400

    # Generate embeddings
    embeddings = model.encode(headlines, show_progress_bar=False)
    stored_headlines = headlines
    stored_embeddings = embeddings

    # Compute similarity matrix
    similarity_matrix = cosine_similarity(embeddings)

    # Find clusters using greedy algorithm (same as production)
    clusters = greedy_cluster(similarity_matrix, threshold)

    # Find pairs above threshold
    pairs = []
    n = len(headlines)
    for i in range(n):
        for j in range(i + 1, n):
            sim = float(similarity_matrix[i][j])
            pairs.append({
                'headline1': headlines[i],
                'headline2': headlines[j],
                'similarity': round(sim, 4),
                'would_cluster': sim >= threshold,
                'idx1': i,
                'idx2': j
            })

    # Sort by similarity descending
    pairs.sort(key=lambda x: x['similarity'], reverse=True)

    # Build cluster info
    cluster_info = []
    unique_clusters = set(clusters)
    for cluster_id in sorted(unique_clusters):
        if cluster_id == -1:
            continue  # Skip noise points
        members = [i for i, c in enumerate(clusters) if c == cluster_id]
        cluster_info.append({
            'cluster_id': cluster_id,
            'size': len(members),
            'headlines': [headlines[i] for i in members],
            'centroid_idx': members[0]  # First member is centroid
        })

    # Noise points (unique articles)
    noise_points = [headlines[i] for i, c in enumerate(clusters) if c == -1]

    # Statistics
    stats = {
        'total_headlines': len(headlines),
        'num_clusters': len(cluster_info),
        'num_unique': len(noise_points),
        'num_duplicates': len(headlines) - len(cluster_info) - len(noise_points),
        'dedup_rate': round((len(headlines) - len(cluster_info) - len(noise_points)) / len(headlines) * 100, 1)
    }

    return jsonify({
        'pairs': pairs[:50],  # Top 50 pairs
        'clusters': cluster_info,
        'noise_points': noise_points,
        'stats': stats,
        'threshold': threshold
    })


@app.route('/compare', methods=['POST'])
def compare_single():
    """Compare a single headline against all stored headlines."""
    global stored_headlines, stored_embeddings

    if stored_embeddings is None or len(stored_headlines) == 0:
        return jsonify({'error': 'No headlines stored. Run analysis first.'}), 400

    data = request.json
    new_headline = data.get('headline', '').strip()

    if not new_headline:
        return jsonify({'error': 'No headline provided'}), 400

    # Encode new headline
    new_embedding = model.encode([new_headline], show_progress_bar=False)

    # Compare against all stored
    similarities = cosine_similarity(new_embedding, stored_embeddings)[0]

    results = []
    for i, (headline, sim) in enumerate(zip(stored_headlines, similarities)):
        results.append({
            'headline': headline,
            'similarity': round(float(sim), 4),
            'idx': i
        })

    results.sort(key=lambda x: x['similarity'], reverse=True)

    return jsonify({
        'query': new_headline,
        'matches': results[:20]  # Top 20 matches
    })


def greedy_cluster(similarity_matrix: np.ndarray, threshold: float) -> list:
    """Greedy clustering algorithm matching production code."""
    n = len(similarity_matrix)
    clusters = [-1] * n  # -1 = noise/unique
    current_cluster = 0

    # Calculate connectivity (how many articles each is similar to)
    connectivity = np.sum(similarity_matrix >= threshold, axis=1) - 1  # -1 for self

    # Process in order of most connected first
    processing_order = np.argsort(-connectivity)

    for i in processing_order:
        if clusters[i] != -1:
            continue  # Already assigned

        # Find all similar articles
        similar = np.where(similarity_matrix[i] >= threshold)[0]
        similar = [j for j in similar if j != i]

        if not similar:
            continue  # No matches, stays as noise

        # Check if any similar articles are already in a cluster
        existing_cluster = None
        for j in similar:
            if clusters[j] != -1:
                existing_cluster = clusters[j]
                break

        if existing_cluster is not None:
            # Join existing cluster
            clusters[i] = existing_cluster
        else:
            # Create new cluster
            clusters[i] = current_cluster
            for j in similar:
                if clusters[j] == -1:
                    clusters[j] = current_cluster
            current_cluster += 1

    return clusters


if __name__ == '__main__':
    print("\n" + "="*60)
    print("EMBEDDINGS SANDBOX")
    print("="*60)
    print("Open http://127.0.0.1:5001 in your browser")
    print("="*60 + "\n")
    app.run(debug=True, port=5001)
