"""Generate cluster analysis report from database."""

import psycopg2
from collections import Counter
import sys

def main():
    # Connect to database
    conn = psycopg2.connect(
        host='127.0.0.1',
        port=5432,
        database='sp500_news',
        user='scraper_user',
        password='dev_password_change_in_production'
    )
    cur = conn.cursor()

    # Get latest embeddings batch
    cur.execute("""
        SELECT cluster_batch_id
        FROM article_clusters
        WHERE clustering_method = 'embeddings'
        ORDER BY created_at DESC
        LIMIT 1
    """)
    batch_id = cur.fetchone()[0]

    print(f"Cluster Report - Batch ID: {batch_id}")
    print("=" * 80)
    print()

    # Get cluster summary
    cur.execute("""
        WITH cluster_info AS (
            SELECT
                ac.cluster_label,
                COUNT(*) as size,
                ARRAY_AGG(a.title ORDER BY ac.is_centroid DESC, a.published_at DESC) as headlines,
                ARRAY_AGG(a.source ORDER BY ac.is_centroid DESC, a.published_at DESC) as sources,
                ARRAY_AGG(ac.is_centroid ORDER BY ac.is_centroid DESC, a.published_at DESC) as centroids
            FROM article_clusters ac
            JOIN articles_raw a ON ac.article_id = a.id
            WHERE ac.cluster_batch_id = %s
                AND ac.cluster_label <> -1
            GROUP BY ac.cluster_label
            HAVING COUNT(*) >= 2
        )
        SELECT
            cluster_label,
            size,
            headlines,
            sources,
            centroids
        FROM cluster_info
        ORDER BY size DESC
    """, (batch_id,))

    clusters = cur.fetchall()

    # Statistics
    total_articles = sum(c[1] for c in clusters)
    cluster_sizes = Counter([c[1] for c in clusters])

    print(f"Total Clusters: {len(clusters)}")
    print(f"Total Articles in Clusters: {total_articles}")
    print(f"Average Cluster Size: {total_articles / len(clusters):.1f}")
    print()

    print("Cluster Size Distribution:")
    for size in sorted(cluster_sizes.keys(), reverse=True):
        count = cluster_sizes[size]
        print(f"  {size:3d} articles: {count:3d} clusters")
    print()

    # Show top 20 clusters
    print("=" * 80)
    print("TOP 20 CLUSTERS (by size)")
    print("=" * 80)
    print()

    for i, (label, size, headlines, sources, centroids) in enumerate(clusters[:20], 1):
        print(f"Cluster #{label} ({size} articles)")
        print("-" * 80)

        # Show all headlines
        for j, (headline, source, is_centroid) in enumerate(zip(headlines, sources, centroids)):
            marker = "[CENTROID]" if is_centroid else "          "
            print(f"  {marker} {headline[:100]}")
            if j >= 9:  # Limit to 10 headlines per cluster
                if len(headlines) > 10:
                    print(f"           ... and {len(headlines) - 10} more")
                break
        print()

    # Check for SEC forms
    cur.execute("""
        SELECT COUNT(DISTINCT a.id)
        FROM article_clusters ac
        JOIN articles_raw a ON ac.article_id = a.id
        WHERE ac.cluster_batch_id = %s
            AND (a.title LIKE '%Form %' OR a.title LIKE '%424B%' OR a.title LIKE '% - %')
    """, (batch_id,))
    sec_count = cur.fetchone()[0]

    print("=" * 80)
    print(f"SEC Forms found in clusters: {sec_count}")
    print("(This shouldn't happen if SEC exclusion is working correctly)")
    print("=" * 80)

    conn.close()

if __name__ == '__main__':
    main()
