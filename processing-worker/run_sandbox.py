#!/usr/bin/env python3
"""Helper script to run sandbox with correct local environment."""

import os
import sys
from pathlib import Path

# Set environment for local postgres connection
os.environ['POSTGRES_HOST'] = 'localhost'
os.environ['POSTGRES_PORT'] = '5432'
os.environ['POSTGRES_DB'] = 'sp500_news'
os.environ['POSTGRES_USER'] = 'scraper_user'
os.environ['POSTGRES_PASSWORD'] = 'dev_password_change_in_production'

# Load OPENAI_API_KEY from parent .env if not already set
if 'OPENAI_API_KEY' not in os.environ:
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith('OPENAI_API_KEY='):
                os.environ['OPENAI_API_KEY'] = line.split('=', 1)[1].strip()
                break

# Import and run sandbox
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from sandbox_labeler import main

if __name__ == '__main__':
    main()
