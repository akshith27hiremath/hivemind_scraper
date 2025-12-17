@echo off
REM Windows wrapper script to run article viewer inside Docker container

docker exec -it sp500_ingestion_worker python /app/view_articles.py %*
