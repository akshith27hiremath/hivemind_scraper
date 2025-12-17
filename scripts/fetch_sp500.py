#!/usr/bin/env python3
"""
Fetch S&P 500 constituent data from Wikipedia and generate seed SQL.

This script scrapes the Wikipedia page listing S&P 500 companies and
generates a SQL insert statement for seeding the database.

Output: database/schema/02_seed_companies.sql
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime


def fetch_sp500_from_wikipedia():
    """Fetch S&P 500 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    print(f"Fetching S&P 500 data from Wikipedia...")
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()

    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the first table (S&P 500 constituents)
    table = soup.find('table', {'class': 'wikitable'})

    # Extract table data
    data = []
    rows = table.find_all('tr')[1:]  # Skip header

    for row in rows:
        cols = row.find_all('td')
        if len(cols) >= 7:
            ticker = cols[0].text.strip()
            name = cols[1].text.strip()
            sector = cols[2].text.strip()
            industry = cols[3].text.strip()

            # CIK is in column 7 (0-indexed: 6)
            cik = cols[6].text.strip() if len(cols) > 6 else None

            data.append({
                'ticker': ticker,
                'name': name,
                'sector': sector,
                'industry': industry,
                'cik': cik
            })

    df = pd.DataFrame(data)
    print(f"Fetched {len(df)} companies")

    return df


def generate_seed_sql(df, output_path):
    """Generate SQL INSERT statements from DataFrame."""

    sql_lines = [
        "-- S&P 500 Companies Seed Data",
        f"-- Generated on {datetime.now().isoformat()}",
        f"-- Total companies: {len(df)}",
        "",
        "-- Insert S&P 500 companies",
        "INSERT INTO companies (ticker, name, sector, industry, cik) VALUES"
    ]

    # Generate VALUES rows
    values = []
    for _, row in df.iterrows():
        ticker = row['ticker'].replace("'", "''")
        name = row['name'].replace("'", "''")
        sector = row['sector'].replace("'", "''")
        industry = row['industry'].replace("'", "''")
        cik = row['cik'].replace("'", "''") if pd.notna(row['cik']) else ''

        cik_value = f"'{cik}'" if cik else "NULL"

        values.append(
            f"    ('{ticker}', '{name}', '{sector}', '{industry}', {cik_value})"
        )

    sql_lines.append(",\n".join(values))
    sql_lines.append("ON CONFLICT (ticker) DO NOTHING;")
    sql_lines.append("")

    # Write to file
    sql_content = "\n".join(sql_lines)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(sql_content)

    print(f"Generated seed SQL: {output_path}")
    print(f"Total INSERT statements: {len(values)}")


def main():
    """Main execution."""
    try:
        # Fetch data
        df = fetch_sp500_from_wikipedia()

        # Generate SQL
        output_path = "database/schema/02_seed_companies.sql"
        generate_seed_sql(df, output_path)

        print("\nSuccess! S&P 500 seed data generated.")
        print(f"Preview of companies:")
        print(df.head(10)[['ticker', 'name', 'sector']])

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
