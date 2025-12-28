@echo off
REM Helper script to run sandbox with correct environment

cd /d %~dp0

REM Set environment for local connection
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5432
set POSTGRES_DB=sp500_news
set POSTGRES_USER=scraper_user
set POSTGRES_PASSWORD=dev_password_change_in_production

REM Load API key from .env
for /f "tokens=1,* delims==" %%a in ('type ..\\.env ^| findstr /r "^OPENAI_API_KEY="') do set %%a=%%b

echo ================================================================================
echo Starting Classification Sandbox
echo ================================================================================
echo.
echo Provider: OpenAI / GPT-4o
echo Database: localhost:5432 (sp500_news)
echo.

python sandbox_labeler.py --provider openai

pause
