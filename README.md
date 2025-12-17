# S&P 500 News Aggregation System - MVP

Automated news aggregation and sentiment analysis system for S&P 500 companies.

## Project Status: Phase 1 - Week 1 Complete

### Current Features
- RSS feed aggregation from 10 financial news sources
- PostgreSQL database with 503 S&P 500 companies
- Automated ingestion worker with 15-minute fetch intervals
- URL-based deduplication
- Docker Compose orchestration
- Comprehensive logging

### Coming in Week 2
- NewsAPI.org integration
- Polygon.io market data integration
- SEC EDGAR filing parsing
- Enhanced error handling and retry logic

## Quick Start

### Prerequisites
- Docker Desktop installed and running
- Git (for version control)

### Setup and Run

1. Clone or navigate to project directory
```bash
cd scraperMVP
```

2. Start the system
```bash
docker-compose up -d
```

This will:
- Build PostgreSQL database with S&P 500 company data
- Build and start ingestion worker
- Begin fetching news every 15 minutes

3. View logs
```bash
# Watch ingestion worker logs
docker-compose logs -f ingestion-worker

# Watch all logs
docker-compose logs -f
```

4. Verify data collection
```bash
# Connect to database
docker exec -it sp500_postgres psql -U scraper_user -d sp500_news

# Check article count
SELECT COUNT(*) FROM articles_raw;

# View recent articles
SELECT title, source, published_at FROM articles_raw ORDER BY fetched_at DESC LIMIT 10;

# Exit database
\q
```

5. Stop the system
```bash
docker-compose down
```

6. Stop and remove all data
```bash
docker-compose down -v
```

## Project Structure

```
scraperMVP/
├── database/
│   ├── Dockerfile                  # PostgreSQL container
│   └── schema/
│       ├── 01_init.sql            # Database schema
│       └── 02_seed_companies.sql  # S&P 500 company data (503 companies)
├── ingestion-worker/
│   ├── Dockerfile                  # Python worker container
│   ├── requirements.txt            # Python dependencies
│   └── src/
│       ├── main.py                # Entry point
│       ├── scheduler.py           # Task scheduler
│       ├── config.py              # Configuration management
│       ├── logger.py              # Logging setup
│       ├── database.py            # Database operations
│       ├── parsers/
│       │   └── rss_parser.py      # RSS feed parser
│       └── api_clients/           # API clients (stubs for Week 2)
│           ├── newsapi_client.py
│           ├── polygon_client.py
│           └── sec_parser.py
├── scripts/
│   ├── fetch_sp500.py             # S&P 500 data fetcher
│   └── requirements.txt           # Script dependencies
├── docker-compose.yml              # Orchestration config
├── .env                           # Environment variables
├── .env.example                   # Template for environment variables
├── .gitignore                     # Git ignore rules
└── README.md                      # This file
```

## Configuration

Edit `.env` file to customize:

```bash
# Database credentials
POSTGRES_USER=scraper_user
POSTGRES_PASSWORD=your_secure_password

# Fetch interval (minutes)
FETCH_INTERVAL_MINUTES=15

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

## RSS Feed Sources

The system currently fetches from 10 financial news sources:

1. Reuters Business
2. MarketWatch
3. Yahoo Finance
4. Seeking Alpha
5. Investing.com
6. CNBC
7. Benzinga
8. TechCrunch
9. The Verge
10. Bloomberg

## Database Schema

### companies
- S&P 500 constituent companies
- Fields: ticker, name, sector, industry, cik

### articles_raw
- All fetched news articles
- Fields: url (unique), title, summary, source, published_at, raw_json
- Automatic URL deduplication

## Development

### Regenerate S&P 500 Data

```bash
# Install script dependencies
pip install -r scripts/requirements.txt

# Fetch latest S&P 500 data from Wikipedia
python scripts/fetch_sp500.py
```

This generates `database/schema/02_seed_companies.sql` with current S&P 500 constituents.

### Rebuild Containers

```bash
# Rebuild after code changes
docker-compose up -d --build

# Rebuild specific service
docker-compose up -d --build ingestion-worker
```

### Database Access

```bash
# Using psql inside container
docker exec -it sp500_postgres psql -U scraper_user -d sp500_news

# Using external psql client (if installed)
psql -h localhost -p 5432 -U scraper_user -d sp500_news
```

## Monitoring

### View Logs
```bash
# Ingestion worker
docker-compose logs -f ingestion-worker

# Database
docker-compose logs -f postgres

# All services
docker-compose logs -f
```

### Check Container Status
```bash
docker-compose ps
```

### Inspect Database
```bash
# Article count by source
SELECT source, COUNT(*) as count
FROM articles_raw
GROUP BY source
ORDER BY count DESC;

# Recent articles
SELECT title, source, published_at
FROM articles_raw
ORDER BY fetched_at DESC
LIMIT 20;

# Articles per day
SELECT DATE(published_at) as date, COUNT(*) as count
FROM articles_raw
WHERE published_at IS NOT NULL
GROUP BY DATE(published_at)
ORDER BY date DESC;
```

## Troubleshooting

### Database connection failed
```bash
# Check if postgres is healthy
docker-compose ps

# View postgres logs
docker-compose logs postgres

# Restart services
docker-compose restart
```

### No articles being fetched
```bash
# Check worker logs for errors
docker-compose logs ingestion-worker

# Verify RSS feeds are accessible
docker exec -it sp500_ingestion_worker python -c "import requests; print(requests.get('https://www.reuters.com/rssfeed/businessnews').status_code)"
```

### Container won't start
```bash
# View build logs
docker-compose up --build

# Remove volumes and rebuild
docker-compose down -v
docker-compose up --build
```

## Roadmap

### Phase 1 - Week 1 (COMPLETE)
- RSS feed aggregation
- Database setup with S&P 500 data
- Docker orchestration
- Basic deduplication

### Phase 1 - Week 2 (Next)
- NewsAPI.org integration
- Polygon.io market data
- SEC EDGAR filing parsing
- Enhanced error handling

### Phase 2
- Sentiment analysis pipeline
- Company-article matching
- Historical trend analysis

### Phase 3
- REST API for data access
- Web dashboard
- Real-time alerts

## License

MIT License - See LICENSE file for details

## Contact

For questions or issues, please open a GitHub issue.
