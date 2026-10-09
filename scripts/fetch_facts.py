"""Download SEC EDGAR company facts for one or more tickers and save the raw JSON.

Usage:
    python scripts/fetch_facts.py AAPL MSFT WMT

Output:
    data/raw/company_tickers.json      ticker-to-CIK map (cached after first download)
    data/raw/<TICKER>_companyfacts.json  one file per company
"""
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def sec_headers():
    """The SEC rejects requests that don't identify who is making them."""
    user_agent = os.getenv("SEC_USER_AGENT")
    if not user_agent:
        sys.exit("SEC_USER_AGENT is missing from .env (format: Your Name your.email@example.com)")
    return {"User-Agent": user_agent}


def get_json(url):
    response = requests.get(url, headers=sec_headers(), timeout=30)
    if response.status_code == 403:
        sys.exit("SEC returned 403 Forbidden. Check that SEC_USER_AGENT in .env has your name and email.")
    response.raise_for_status()
    time.sleep(0.2)  # stay well under the SEC's limit of 10 requests per second
    return response.json()


def load_ticker_map():
    """Return {TICKER: (ten-digit CIK, company name)}."""
    cache = RAW_DIR / "company_tickers.json"
    if cache.exists():
        data = json.loads(cache.read_text())
    else:
        data = get_json(TICKERS_URL)
        cache.write_text(json.dumps(data))
    return {
        row["ticker"].upper(): (str(row["cik_str"]).zfill(10), row["title"])
        for row in data.values()
    }


def main(tickers):
    if not tickers:
        sys.exit(__doc__)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ticker_map = load_ticker_map()

    for ticker in (t.upper().replace(".", "-") for t in tickers):  # SEC writes BRK.B as BRK-B
        if ticker not in ticker_map:
            print(f"{ticker}: not found in the SEC ticker map. Skipping.")
            continue
        cik, name = ticker_map[ticker]
        facts = get_json(FACTS_URL.format(cik=cik))
        out_path = RAW_DIR / f"{ticker}_companyfacts.json"
        out_path.write_text(json.dumps(facts, indent=2))
        n_tags = len(facts.get("facts", {}).get("us-gaap", {}))
        size_mb = out_path.stat().st_size / 1_000_000
        print(f"{ticker}: {name} | CIK {cik} | {n_tags} us-gaap tags | saved {out_path.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main(sys.argv[1:])
