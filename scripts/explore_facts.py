"""Print the structure of a saved companyfacts file, focused on this project's six metrics.

Usage:
    python scripts/explore_facts.py AAPL

Run scripts/fetch_facts.py first so data/raw/<TICKER>_companyfacts.json exists.
"""
import json
import sys
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Tags companies commonly use for each metric. Which ones a company uses, and when,
# is exactly what this script is meant to reveal.
CANDIDATE_TAGS = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities", "LiabilitiesAndStockholdersEquity"],
    "diluted_eps": ["EarningsPerShareDiluted"],
}


def ten_k_facts(concept):
    """All facts for a tag that came from 10-K filings, across every unit."""
    return [
        f
        for unit_facts in concept["units"].values()
        for f in unit_facts
        if f.get("form") == "10-K"
    ]


def latest_filed(concept):
    return max((f["filed"] for f in ten_k_facts(concept)), default="")


def describe_tag(us_gaap, tag):
    if tag not in us_gaap:
        print(f"    {tag}: not used by this company")
        return
    concept = us_gaap[tag]
    for unit, facts in concept["units"].items():
        tenk = [f for f in facts if f.get("form") == "10-K"]
        ends = sorted(f["end"] for f in tenk)
        span = f"period ends {ends[0]} to {ends[-1]}" if ends else "no 10-K facts"
        print(f"    {tag} [{unit}]: {len(facts)} facts total, {len(tenk)} from 10-Ks, {span}")


def show_one_filing(us_gaap, tag):
    """List every value one 10-K reported for a tag. Notice that fy is the same on every row."""
    tenk = ten_k_facts(us_gaap[tag])
    if not tenk:
        return
    latest_accn = max(tenk, key=lambda f: f["filed"])["accn"]
    rows = sorted((f for f in tenk if f["accn"] == latest_accn), key=lambda f: (f["end"], f.get("start", "")))
    print(f"\nEvery {tag} value in the most recent 10-K (accession {latest_accn}):")
    print(f"    {'start':<12}{'end':<12}{'fy':<6}{'fp':<4}{'value':>22}")
    for f in rows:
        print(f"    {f.get('start', '-'):<12}{f['end']:<12}{str(f.get('fy')):<6}{str(f.get('fp')):<4}{f['val']:>22,}")
    print("    -> fy describes the FILING, not the period. Use start/end to know which year a value belongs to.")


def main(ticker):
    path = RAW_DIR / f"{ticker.upper()}_companyfacts.json"
    if not path.exists():
        sys.exit(f"{path} not found. Run: python scripts/fetch_facts.py {ticker.upper()}")
    data = json.loads(path.read_text())

    print(f"{data.get('entityName')} (CIK {data.get('cik')})")
    print("Taxonomies: " + ", ".join(f"{name} ({len(tags)} tags)" for name, tags in data["facts"].items()))

    us_gaap = data["facts"].get("us-gaap", {})
    for metric, tags in CANDIDATE_TAGS.items():
        print(f"\n{metric}")
        for tag in tags:
            describe_tag(us_gaap, tag)

    revenue_tags = [t for t in CANDIDATE_TAGS["revenue"] if t in us_gaap]
    if revenue_tags:
        current = max(revenue_tags, key=lambda t: latest_filed(us_gaap[t]))
        show_one_filing(us_gaap, current)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
