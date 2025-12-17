# Article Viewer Guide

Simple command-line tool to view and filter scraped news articles from your database.

## Quick Start

Since the script needs to access the database inside Docker, use this command format:

```bash
docker exec sp500_ingestion_worker python view_articles.py [OPTIONS]
```

## Common Commands

### 1. View Latest Articles (Default: 20)
```bash
docker exec sp500_ingestion_worker python view_articles.py
```

### 2. Show More Articles
```bash
docker exec sp500_ingestion_worker python view_articles.py --limit 50
```

### 3. Show Database Statistics
```bash
docker exec sp500_ingestion_worker python view_articles.py --stats
```

**Output:**
- Total article count
- Articles by source
- Recent activity (last 24 hours)
- Date range (oldest/newest articles)

### 4. List All Sources
```bash
docker exec sp500_ingestion_worker python view_articles.py --sources
```

### 5. Filter by Source
```bash
docker exec sp500_ingestion_worker python view_articles.py --source "Yahoo Finance" --limit 10
```

### 6. Search by Keyword
```bash
# Search for articles mentioning "Tesla"
docker exec sp500_ingestion_worker python view_articles.py --keyword "Tesla"

# Search for articles mentioning "Nvidia"
docker exec sp500_ingestion_worker python view_articles.py --keyword "Nvidia" --limit 10
```

### 7. Recent Articles (Last N Days)
```bash
# Articles from last 24 hours
docker exec sp500_ingestion_worker python view_articles.py --days 1

# Articles from last 7 days
docker exec sp500_ingestion_worker python view_articles.py --days 7
```

### 8. Combine Filters
```bash
# Nvidia articles from Yahoo Finance in last 3 days
docker exec sp500_ingestion_worker python view_articles.py \
  --source "Yahoo Finance" \
  --keyword "Nvidia" \
  --days 3 \
  --limit 20
```

## Interactive Mode

For a menu-driven experience:

```bash
docker exec -it sp500_ingestion_worker python view_articles.py --interactive
```

**Interactive Menu:**
1. View latest articles
2. Filter by source
3. Search by keyword
4. Show statistics
5. List all sources
q. Quit

## Examples

### Example 1: Quick Stats Check
```bash
$ docker exec sp500_ingestion_worker python view_articles.py --stats

DATABASE STATISTICS
===================
Total Articles: 933

Articles by Source:
  Yahoo Finance                    306
  Investing.com                    155
  Seeking Alpha                    119
  Bloomberg                         68
  ...
```

### Example 2: Find Tesla News
```bash
$ docker exec sp500_ingestion_worker python view_articles.py --keyword "Tesla" --limit 5

[1] Tesla Stock Surges on Delivery Numbers
Source: Yahoo Finance
Published: 2025-12-17 18:30:00
URL: https://...
```

### Example 3: Browse Seeking Alpha Articles
```bash
$ docker exec sp500_ingestion_worker python view_articles.py --source "Seeking Alpha (AAPL)" --limit 10
```

## Windows Users

You can use the `view.bat` wrapper for shorter commands:

```cmd
view.bat --stats
view.bat --keyword "Apple"
view.bat --limit 50
```

## Unix/Linux Users

Use the `view.sh` wrapper:

```bash
./view.sh --stats
./view.sh --keyword "Apple"
./view.sh --limit 50
```

## Available Options

| Option | Description | Example |
|--------|-------------|---------|
| `--limit N` | Show N articles (default: 20) | `--limit 50` |
| `--source "Name"` | Filter by source name | `--source "Yahoo Finance"` |
| `--keyword "Text"` | Search in title/summary | `--keyword "Tesla"` |
| `--days N` | Articles from last N days | `--days 7` |
| `--stats` | Show database statistics | `--stats` |
| `--sources` | List all available sources | `--sources` |
| `--interactive` or `-i` | Interactive menu mode | `-i` |

## Tips

1. **Case-insensitive search**: Keyword searches work regardless of case
2. **Partial matches**: Keyword "tesla" will match "Tesla", "TESLA", "tesla's", etc.
3. **Combine filters**: Use multiple options together for precise queries
4. **Check stats first**: Use `--stats` to see what's in your database

## Troubleshooting

### "Cannot connect to database"
- Make sure Docker containers are running: `docker-compose ps`
- Restart if needed: `docker-compose up -d`

### "No articles found"
- Check if articles exist: `--stats`
- Try broader search: remove filters, increase `--limit`
- Check source name: use `--sources` to see exact names

### "Permission denied" on view.sh
```bash
chmod +x view.sh
```

## Future Enhancements (Coming in Week 3)

Once we implement Named Entity Recognition (NER) in Week 3, you'll be able to:
- Filter by stock ticker: `--ticker AAPL`
- Show company mentions: `--companies`
- Filter by sentiment: `--sentiment positive`
- See relevance scores

## Need Help?

```bash
docker exec sp500_ingestion_worker python view_articles.py --help
```
