# StockScanner

An options premium-selling scanner. Enter a ticker and get IV rank/score,
technicals (EMA, ATR, support/resistance), earnings distance & expected move,
liquidity (bid/ask spread, open interest), unusual options activity, insider
and congressional trading signals, and correlation to your existing
positions -- rolled up into one call:

- 🟢 **SELL PUT SPREAD**
- 🟡 **WAIT**
- 🔴 **AVOID**

This is a decision-support tool, not investment advice. All output is
generated from free public data sources and disclosed heuristics -- see
"Data sources & known limitations" below before trusting any single number.

## Architecture

- **Backend**: Python / FastAPI (`backend/app`). Fetches market data via
  [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance), computes
  technicals and options analytics locally, and pulls insider/congressional
  trading data from free public sources.
- **Frontend**: a single dependency-free HTML/CSS/JS page
  (`backend/app/static`), served directly by FastAPI. No build step.

## Running it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd backend
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000, enter a ticker (and optionally a comma-separated
list of existing position tickers for the correlation check), and click
Analyze.

API only: `GET /api/analyze?ticker=AAPL&positions=SPY,QQQ`

### Offline sanity test

`backend/tests/test_offline_pipeline.py` exercises the indicator/options/
signal-engine pipeline against synthetic data (no network required):

```bash
cd backend && python3 -m tests.test_offline_pipeline
```

## What each metric means

| Metric | How it's computed |
|---|---|
| IV Score / IV Rank | ATM implied volatility (from the nearest ~30-day option chain) scored against a **realized-volatility-based proxy range**, since free historical IV data doesn't exist. See disclosure below. |
| EMA | 9/20/50/200-day exponential moving averages on daily closes. |
| Support & Resistance | Clustered swing highs/lows (local extrema) over the trailing ~120 trading days. |
| Earnings date / distance | From `yfinance`'s earnings calendar. |
| ATR | 14-day Wilder average true range. |
| Expected move | ATM straddle price (primary) with an IV·√t formula cross-check, to the nearest ~30-day expiration. |
| Earnings distance | Days from today to the next earnings date; a hard signal cutoff applies inside 3 days. |
| Bid/ask spread | Stock quote spread and ATM option spread, both as % of mid. |
| OI | Open interest summed across ATM strikes on the nearest ~30-day expiration. |
| Whale activity | Statistical volume-outlier detection within the option chain (z-score vs. same-side average) plus put/call volume skew. **Not** a real block-trade tape. |
| Insider buying | Recent Form 4 filings via openinsider.com. |
| Congress activity | House/Senate trading disclosures via public data dumps, with explicit staleness detection (see below). |
| Correlation | Pearson correlation of trailing ~6-month daily returns vs. tickers you list as existing positions. |

## Recommendation logic

`backend/app/services/signal_engine.py` is a transparent, additive scoring
model (starts at 50/100) -- every factor above nudges the score up or down
with a human-readable reason attached. Thresholds: **≥65 → SELL PUT SPREAD**,
**40-64 → WAIT**, **<40 → AVOID**, with a hard override to WAIT when earnings
land within 3 days (gap risk). The full reasoning list is returned by the API
and shown in the UI under "Why this recommendation."

## Data sources & known limitations

- **Market data / options chains / earnings**: [yfinance](https://github.com/ranaroussi/yfinance)
  (unofficial Yahoo Finance client, free, no key). Subject to Yahoo's rate
  limits and occasional breakage when Yahoo changes its endpoints.
- **IV Rank**: true IV Rank requires a 52-week history of implied volatility,
  which isn't available for free. This app approximates the range using
  trailing realized volatility (HV20) as a proxy and clearly labels it
  "(approx.)" in the API response and UI. Treat it as directional, not exact.
- **Whale activity**: real block-trade/sweep data is a paid product (e.g.
  Unusual Whales, FlowAlgo). This app approximates it via volume/OI outlier
  detection on the public option chain, which will miss iceberg/dark-pool
  activity and can false-positive on illiquid names.
- **Insider buying**: scraped from [openinsider.com](http://openinsider.com),
  a public aggregator of SEC Form 4 filings. If the site's HTML structure
  changes or blocks automated requests, this section degrades gracefully to
  "unavailable" rather than failing the whole request.
- **Congress activity**: pulled from the House Stock Watcher API and the
  Senate Stock Watcher GitHub data mirror. **These community-maintained
  projects have a history of going stale or disappearing** -- the app
  detects this (if the newest record on file is >45 days old) and marks the
  result `"stale": true` with a warning, rather than silently implying "no
  recent trades." The signal engine ignores congress data when it's flagged
  stale.
- All external calls are cached in-memory (5-60 min TTL depending on source)
  and fail gracefully -- a down data source degrades that one card, it never
  crashes the whole analysis.

## Disclaimer

Nothing in this app is financial advice. Options trading involves
substantial risk. Verify all data (especially IV Rank, whale activity, and
congress/insider signals, which are heuristic approximations from free data)
independently before trading.
