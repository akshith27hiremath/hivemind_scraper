# Web Dashboard Guide

## 🎉 Your Dashboard is Live!

Access your web dashboard at: **http://localhost:5000**

---

## Features

### 1. **Real-Time Statistics**
- Total articles in database
- Articles added in last 24 hours
- Number of unique data sources
- System health status (services healthy count)

### 2. **Article Browser**
- View latest articles with title, summary, source, and publish date
- Click "Read More" to open the full article in a new tab
- Pagination for easy navigation through thousands of articles

### 3. **Advanced Filtering**

**Filter by Source:**
- Dropdown shows all available sources with article counts
- Examples: "Yahoo Finance (306)", "Seeking Alpha (119)"

**Search by Keyword:**
- Search articles by keyword in title or summary
- Case-insensitive
- Examples: "Tesla", "Nvidia", "earnings"

**Time Range:**
- Last 24 Hours
- Last 7 Days
- Last 30 Days
- All Time (default)

**Results Limit:**
- 20, 50, or 100 articles per page

### 4. **System Health Monitor**

Real-time health checks for all data sources:

**Database**
- Connection status
- Query performance

**Finnhub API**
- API key validation
- Rate limit status
- Test query results

**Alpha Vantage API**
- API key validation
- Rate limit status
- Sentiment data availability

**SEC EDGAR**
- Feed accessibility
- CIK mapping status

**RSS Feeds**
- Active feeds count (10 total)
- Recent activity (last 30 minutes)
- Health status: Healthy (7+), Degraded (4-6), Unhealthy (<4)

---

## Health Status Indicators

| Color | Status | Meaning |
|-------|--------|---------|
| 🟢 Green | Healthy | Service operational |
| 🟡 Yellow | Warning | Minor issues, still functional |
| 🟠 Orange | Degraded | Reduced functionality |
| 🔴 Red | Error/Unhealthy | Service down or failing |

---

## How to Use

### Quick Stats Check
1. Open http://localhost:5000
2. View the 4 stat cards at the top
3. See overall health in the navigation bar

### Browse Latest News
1. Main page shows latest 50 articles by default
2. Scroll down to see articles
3. Click "Read More" to open full article

### Filter Articles

**Example 1: Find Tesla News**
```
1. Leave Source as "All Sources"
2. Type "Tesla" in Keyword field
3. Select "Last 7 Days" for time range
4. Click "Filter" button
```

**Example 2: Browse Yahoo Finance**
```
1. Select "Yahoo Finance" from Source dropdown
2. Leave other fields empty
3. Click "Filter" button
```

**Example 3: Recent Nvidia Coverage**
```
1. Select "All Sources"
2. Type "Nvidia" in Keyword
3. Select "Last 24 Hours"
4. Click "Filter"
```

### Check System Health
1. Scroll to "System Health" section
2. View status of each service
3. Click "Check Now" to refresh health checks
4. Each service shows:
   - Status indicator (green/yellow/red dot)
   - Service name
   - Status message
   - Last check time

### Auto-Refresh
- System health auto-refreshes every 5 minutes
- Click "Refresh" button (top right) to manually update all data

---

## API Endpoints

The dashboard exposes several API endpoints you can use:

### GET /api/stats
Returns database statistics.

**Example:**
```bash
curl http://localhost:5000/api/stats
```

**Response:**
```json
{
  "total_articles": 933,
  "recent_24h": 933,
  "oldest_article": "2023-12-15T20:40:28",
  "newest_article": "2025-12-17T20:16:32",
  "unique_sources": 14
}
```

### GET /api/sources
Returns list of all sources with article counts.

**Example:**
```bash
curl http://localhost:5000/api/sources
```

### GET /api/articles
Returns filtered articles.

**Query Parameters:**
- `source`: Filter by source name
- `keyword`: Search keyword
- `days`: Articles from last N days
- `limit`: Number of results (default: 50)
- `offset`: Pagination offset (default: 0)

**Example:**
```bash
# Get latest 10 articles about Tesla
curl "http://localhost:5000/api/articles?keyword=Tesla&limit=10"

# Get Yahoo Finance articles from last 24h
curl "http://localhost:5000/api/articles?source=Yahoo%20Finance&days=1"
```

### GET /api/health
Returns health status of all services.

**Example:**
```bash
curl http://localhost:5000/api/health | python -m json.tool
```

**Response:**
```json
{
  "timestamp": "2025-12-17T20:30:00",
  "overall": "healthy",
  "services": {
    "database": {
      "status": "healthy",
      "message": "Connection successful"
    },
    "finnhub": {
      "status": "healthy",
      "message": "Fetched 156 test articles",
      "api_key_configured": true,
      "rate_limit_status": "ok"
    },
    ...
  }
}
```

---

## Understanding Health Status

### Overall Health
- **Healthy**: All services operational
- **Warning**: Some minor issues, system functional
- **Degraded**: One or more services experiencing problems

### Service-Specific Status

**Database: "healthy"**
- ✅ Connection successful
- ✅ Queries executing normally

**Finnhub/Alpha Vantage: "healthy"**
- ✅ API key valid
- ✅ Test queries successful
- ✅ No rate limiting

**Finnhub/Alpha Vantage: "rate_limited"**
- ⚠️ Hit API rate limit (60/min or 500/day)
- ⏳ Wait for rate limit reset
- 💡 Scheduler handles this automatically

**SEC EDGAR: "healthy"**
- ✅ CIK mapping complete
- ✅ Test filing fetch successful

**RSS Feeds: "healthy" (7+ active)**
- ✅ 70%+ feeds working
- ✅ Recent articles from feeds

**RSS Feeds: "degraded" (4-6 active)**
- ⚠️ 40-60% feeds working
- ⚠️ Some feeds may be temporarily down

**RSS Feeds: "unhealthy" (<4 active)**
- ❌ <40% feeds working
- ❌ Check network/feed availability

---

## Troubleshooting

### Dashboard won't load
```bash
# Check if container is running
docker-compose ps

# Check logs
docker-compose logs web-dashboard

# Restart
docker-compose restart web-dashboard
```

### "Cannot connect to database" error
```bash
# Restart database
docker-compose restart postgres

# Rebuild dashboard
docker-compose build web-dashboard && docker-compose up -d web-dashboard
```

### Health check shows all services as errors
```bash
# Wait 10 seconds and click "Check Now" again
# Or refresh the page

# If persists, check logs
docker-compose logs web-dashboard --tail=50
```

### API rate limited
- **Finnhub**: Wait until next minute (60/min limit)
- **Alpha Vantage**: Wait 12 seconds (5/min limit) or until next day (500/day limit)
- **Automatic handling**: Scheduler will retry after delays

### Filters not working
- Clear all filters and try again
- Check JavaScript console for errors (F12 in browser)
- Make sure keyword doesn't have special characters

---

## Performance Tips

1. **Use specific filters** instead of loading all articles
2. **Limit results** to 20-50 for faster loading
3. **Recent time ranges** (24h, 7d) are faster than "All Time"
4. **Keyword search** uses database index (fast)
5. **Pagination** click Next/Previous instead of increasing limit

---

## What's Next?

After Week 3 (NER implementation), the dashboard will support:
- ✨ **Filter by Stock Ticker**: Select AAPL, MSFT, GOOGL, etc.
- ✨ **Company Mentions**: See all tickers mentioned in articles
- ✨ **Sentiment Filtering**: Filter by positive/negative/neutral sentiment
- ✨ **Relevance Scores**: Sort by how relevant article is to a company

---

## Access From External Devices

If you want to access the dashboard from other devices on your network:

1. Find your computer's local IP:
   ```bash
   # Windows
   ipconfig | findstr IPv4

   # Mac/Linux
   ifconfig | grep inet
   ```

2. Access from other device:
   ```
   http://YOUR_IP:5000
   ```

**Security Note**: Dashboard has no authentication in MVP. Only use on trusted networks.

---

## Tech Stack

- **Backend**: Flask (Python web framework)
- **Frontend**: Bootstrap 5 + Vanilla JavaScript
- **Database**: PostgreSQL (via psycopg2)
- **Icons**: Bootstrap Icons
- **Styling**: Gradient navbar, card-based design, hover effects

---

## Support

**Documentation:**
- Main implementation: `PHASE1_WEEK2_COMPLETE.md`
- CLI viewer: `VIEWER_GUIDE.md`
- This guide: `WEB_DASHBOARD_GUIDE.md`

**Quick Commands:**
```bash
# View logs
docker-compose logs web-dashboard -f

# Restart dashboard
docker-compose restart web-dashboard

# Rebuild (after code changes)
docker-compose build web-dashboard && docker-compose up -d
```

---

**Enjoy your dashboard!** 🚀📊
