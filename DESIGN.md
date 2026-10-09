# Design

## Principle

Every number a reader sees must be traceable to a value in an SEC filing. Python loads and computes all figures. The LLM is only allowed to describe figures it was given, and a checker verifies that it did so accurately.

## Data source

- **Ticker to CIK:** `https://www.sec.gov/files/company_tickers.json`. CIKs are padded to ten digits for API calls.
- **Company facts:** `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`. Values sit under `facts → us-gaap → <tag> → units → <unit>` as a list of facts. Each fact has `start` (duration items only), `end`, `val`, `accn`, `fy`, `fp`, `form` and `filed`.
- **Access rules:** every request sends a `User-Agent` header with a name and email, and requests stay under 10 per second.

## Metrics and XBRL tags

Companies use different tags for the same concept, and some change tags over time. Each metric maps to a list of candidate tags. The priority order is finalized per company during exploration and verification against the 10-Ks.

| Metric | Candidate tags | Period type | Unit |
|---|---|---|---|
| `revenue` | `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `RevenueFromContractWithCustomerIncludingAssessedTax`, `SalesRevenueNet` (common before ASC 606) | Duration | USD |
| `net_income` | `NetIncomeLoss` (attributable to the parent; preferred). `ProfitLoss` includes noncontrolling interests and is used only as a documented fallback. | Duration | USD |
| `operating_cash_flow` | `NetCashProvidedByUsedInOperatingActivities`, `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations` | Duration | USD |
| `total_assets` | `Assets` | Instant | USD |
| `total_liabilities` | `Liabilities`. If a company doesn't tag it, derived as `LiabilitiesAndStockholdersEquity` minus `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`, and marked as derived. | Instant | USD |
| `diluted_eps` | `EarningsPerShareDiluted` | Duration | USD/shares |

## Selecting one annual value per period

**The trap:** a fact's `fy` field is the fiscal year of the *filing*, not of the value. A single 10-K reports two or three years of income statement figures, and all of them carry the same `fy`. Keying on `fy` produces several different values for the same "year."

**The rule:**

1. Keep only facts from 10-K filings (including 10-K/A amendments).
2. For duration metrics, keep only periods of roughly one year (350–380 days, which allows for 52/53-week fiscal years). This drops quarterly figures that sometimes appear in 10-Ks.
3. Balance sheet metrics are instants, identified by `end` alone.
4. For each metric and period end, keep the value from the most recently filed 10-K.

**Why the latest filing wins:** it means restated figures are used, so both years in a comparison are on the same basis. Stock splits are the clearest case. After a split, prior-year EPS is restated in later filings, and mixing pre-split and post-split EPS would produce meaningless changes. The trade-off is that figures may differ from what was originally reported, which will be documented.

## Planned schema

```sql
CREATE TABLE companies (
    cik              TEXT PRIMARY KEY,      -- ten digits, zero-padded
    ticker           TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    fiscal_year_end  TEXT                   -- informational, e.g. late September
);

CREATE TABLE financials (
    id            INTEGER PRIMARY KEY,
    cik           TEXT NOT NULL REFERENCES companies(cik),
    metric        TEXT NOT NULL,            -- revenue, net_income, ...
    fiscal_year   INTEGER NOT NULL,
    period_start  TEXT,                     -- NULL for balance sheet (instant) values
    period_end    TEXT NOT NULL,
    value         NUMERIC NOT NULL,         -- whole dollars for USD, decimals for EPS
    unit          TEXT NOT NULL,            -- USD or USD/shares
    xbrl_tag      TEXT NOT NULL,            -- which tag the value came from
    is_derived    INTEGER NOT NULL DEFAULT 0,
    form          TEXT NOT NULL,
    accession_no  TEXT NOT NULL,            -- links back to the source filing
    filed         TEXT NOT NULL,
    UNIQUE (cik, metric, period_end)
);

CREATE TABLE summaries (
    id              INTEGER PRIMARY KEY,
    cik             TEXT NOT NULL REFERENCES companies(cik),
    fiscal_year     INTEGER NOT NULL,       -- the current year being summarized
    model           TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    raw_response    TEXT NOT NULL,          -- kept even when parsing fails
    parsed_json     TEXT,                   -- NULL if the response was malformed
    created_at      TEXT NOT NULL
);

CREATE TABLE validation_flags (
    id             INTEGER PRIMARY KEY,
    summary_id     INTEGER NOT NULL REFERENCES summaries(id),
    check_type     TEXT NOT NULL,           -- value_mismatch, change_mismatch, ...
    metric         TEXT,
    expected       TEXT,
    actual         TEXT,
    detail         TEXT,
    review_status  TEXT NOT NULL DEFAULT 'open'  -- open, confirmed_error, false_positive
);
```

## Summary format

The model cites every figure by metric and fiscal year, using raw units, so the checker can look it up exactly rather than guessing what a rounded number refers to.

```json
{
  "ticker": "AAPL",
  "current_fiscal_year": 2024,
  "prior_fiscal_year": 2023,
  "highlights": [
    {
      "metric": "revenue",
      "current_value": 391035000000,
      "prior_value": 383285000000,
      "pct_change": 2.0,
      "comment": "Revenue rose 2.0% year over year."
    }
  ],
  "overview": "Short narrative built only from the figures above."
}
```

## Validation layer

| Check | What it catches | Tolerance |
|---|---|---|
| Figure lookup | A cited value that doesn't match the database | 0.5% relative, to allow rounding |
| Year check | A figure attributed to the wrong fiscal year | Exact |
| Change recompute | A percentage change that differs from Python's calculation | 0.1 percentage points |
| Direction | Prose that says "increased" when the change is negative, or the reverse | Exact |
| Narrative number scan | A number in the free text that can't be traced to any input value or computed change | Same as figure lookup |
| Undefined change | A percentage change cited when the prior value is zero or negative | Exact |
| Unsupported explanation | Causal language such as "driven by" or "due to," which the figures alone can't support | Flagged for human review, not failed |

Every flag goes to the `validation_flags` table with `review_status = 'open'`. During human review, each flag is marked either `confirmed_error` or `false_positive`. Tests plant wrong figures to prove the checker works, but the reported count of incorrect figures comes only from flags confirmed during review of real summaries.

## Open questions

- Revenue tag priority for companies that report more than one revenue tag.
- Fiscal-year labeling for 52/53-week years that end in the first weeks of a calendar year, where the year of the end date doesn't match the company's own label.
- Whether to also store as-originally-reported values alongside restated ones.
- How often total liabilities has to be derived, and whether the derivation matches the balance sheet in each 10-K.
