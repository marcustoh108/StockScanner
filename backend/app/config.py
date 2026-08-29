import os

# Public, no-API-key data sources used for congress trading disclosures.
# House Stock Watcher's bulk dump; if this endpoint changes/discontinues, the
# congress service degrades gracefully (returns "unavailable") rather than erroring.
HOUSE_STOCK_WATCHER_URL = "https://housestockwatcher.com/api/transactions"
# Senate Stock Watcher's data is mirrored on GitHub and served raw (more
# reliable than the project's S3 bucket, which now denies public reads).
SENATE_STOCK_WATCHER_URL = (
    "https://raw.githubusercontent.com/timothycarambat/"
    "senate-stock-watcher-data/master/aggregate/all_transactions.json"
)

# Public insider-trading aggregator (SEC Form 4 data), no API key required.
OPENINSIDER_URL = "http://openinsider.com/screener?s={ticker}"

REQUEST_TIMEOUT = float(os.environ.get("SCANNER_HTTP_TIMEOUT", 12))
CACHE_TTL_SECONDS = int(os.environ.get("SCANNER_CACHE_TTL", 900))
HTTP_USER_AGENT = "StockScanner/1.0 (educational options analysis tool)"
