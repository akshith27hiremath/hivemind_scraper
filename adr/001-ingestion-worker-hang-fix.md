# ADR-001: Ingestion Worker Hang Prevention

**Date**: 2026-02-14
**Status**: Accepted
**Impact**: Critical (2-day production outage)

## Context

On Feb 12, 2026 at 10:04:29 UTC, the ingestion worker froze while fetching the Investing.com RSS feed. The container stayed "Up" but ingested zero articles for 48+ hours. The processing worker continued running but had nothing new to process. The dashboard showed "degraded" status.

The system had been running without incident for ~2 months prior.

## Root Cause

`feedparser.parse(feed_url)` on line 81 of `rss_parser.py` makes an HTTP request with **no timeout**. The `feedparser` library uses `urllib.request.urlopen()` internally, which defaults to `socket.timeout = None` (infinite).

When Investing.com accepted the TCP connection but stopped sending data mid-response (likely a server stall, rate-limit, or half-open connection), Python's `socket.recv()` blocked forever. No exception was raised. The thread was permanently stuck in a kernel-level socket wait.

### Why It Killed Everything

1. **Single-threaded scheduler**: The `schedule` library runs jobs synchronously. One hung feed blocks ALL tasks (RSS, Seeking Alpha, SEC, Finnhub, Alpha Vantage) permanently.

2. **No Docker healthcheck**: The container had `restart: unless-stopped` but no healthcheck. Docker only restarts containers that exit. A hung process never exits, so Docker saw nothing wrong.

3. **try/except useless for hangs**: The scheduler wraps tasks in try/except, but a blocked socket never raises an exception. The failure counter was never incremented.

### Why It Never Happened Before

This failure requires a specific, rare network condition:
- The remote server must accept the TCP handshake (SYN/SYN-ACK/ACK completes)
- Then stop sending data mid-response (no FIN, no RST, no data)
- This creates a half-open connection that `recv()` waits on indefinitely

Normal failures (DNS timeout, connection refused, HTTP 500, server down) all raise exceptions and are caught by the existing try/except. This is a ~0.01% edge case per connection. But with 10 feeds x 96 fetches/day = 960 connections/day, over 2 months (~57,600 connections), hitting it once is statistically expected.

The irony: every other parser (Seeking Alpha, SEC, Finnhub, Alpha Vantage) uses `requests` with explicit 10-second timeouts. The RSS parser was the only one using `feedparser.parse(url)` directly.

### How Long Would It Have Lasted

**Forever.** The hang would have persisted until:
- Someone manually restarted the container, OR
- The droplet rebooted (no scheduled reboots), OR
- The remote server sent a TCP RST (could take days/weeks/never)

There was no self-recovery mechanism. The container would have stayed "Up" with zero ingestion indefinitely.

## Decision

Implement 4 layers of defense-in-depth:

### Layer 1: Fix the root cause (rss_parser.py)

Replace `feedparser.parse(url)` with `requests.get(url, timeout=(10, 30))` followed by `feedparser.parse(response.content)`.

- 10-second connect timeout, 30-second read timeout
- Uses a `requests.Session` with User-Agent header
- On timeout: `requests.exceptions.Timeout` is raised, caught by existing try/except, feed is skipped, next feed proceeds

### Layer 2: Global socket timeout safety net (main.py)

`socket.setdefaulttimeout(60)` set at process startup.

- Catches ANY library that forgets to set its own timeout
- 60 seconds is generous enough to not interfere with normal operations
- Last-resort backstop only

### Layer 3: Heartbeat file (scheduler.py)

Write `/tmp/heartbeat` with current timestamp after each `schedule.run_pending()` loop iteration.

- If the scheduler hangs inside a task, the heartbeat goes stale
- Enables external monitoring (Docker healthcheck)

### Layer 4: Docker healthcheck (docker-compose.yml)

```yaml
healthcheck:
  test: ["CMD-SHELL", "python -c \"import os,time; assert time.time()-os.path.getmtime('/tmp/heartbeat')<300\""]
  interval: 60s
  timeout: 10s
  retries: 3
  start_period: 120s
```

- Checks heartbeat file is less than 5 minutes old
- Checked every 60 seconds, 3 retries before marking unhealthy
- 120-second start period allows for initial SEC EDGAR fetch
- Combined with `restart: unless-stopped`, Docker will restart the container on detected hang

## Failure Scenarios After Fix

| Scenario | Layer 1 | Layer 2 | Layer 3+4 | Outcome |
|----------|---------|---------|-----------|---------|
| Feed returns slowly | requests timeout at 30s | N/A | N/A | Feed skipped, others proceed |
| Feed hangs forever | requests timeout at 30s | socket timeout at 60s | Heartbeat stale → restart | Max 30s delay per feed |
| Unknown library hangs | N/A | socket timeout at 60s | Heartbeat stale → restart | Max 5 min before restart |
| All defenses fail | N/A | N/A | Heartbeat stale → container restart | Max ~7 min before restart |

## Files Changed

| File | Change |
|------|--------|
| `ingestion-worker/src/parsers/rss_parser.py` | `requests.get()` with timeout instead of `feedparser.parse(url)` |
| `ingestion-worker/src/main.py` | `socket.setdefaulttimeout(60)` |
| `ingestion-worker/src/scheduler.py` | Heartbeat file write in main loop |
| `docker-compose.yml` | Healthcheck on ingestion-worker |

## Consequences

- RSS feeds that are slow (>30s response) will be skipped rather than waited on. This is acceptable — the feed will be retried in 15 minutes.
- The global socket timeout may affect very slow legitimate operations. At 60 seconds, this is unlikely to be a problem for any current operation.
- Docker healthcheck adds minimal overhead (one Python invocation per minute).

## Vulnerability Audit

| Parser | Has Timeout | Has Retry | Vulnerable |
|--------|-------------|-----------|------------|
| RSS (feedparser) | **NOW: 10s+30s** | No (skips feed) | **Fixed** |
| Seeking Alpha | 10s | 3x backoff | No |
| SEC EDGAR | 10s | 3x 2s delay | No |
| Finnhub | 10s | 3x exponential | No |
| Alpha Vantage | 10s | 3x 3s delay | No |
| SEC CIK Mapper | 30s | No | No |
