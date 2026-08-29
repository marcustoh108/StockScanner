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
  technicals and options analytics locally, pulls insider/congressional
  trading data from free public sources, and owns user accounts +
  subscription state (SQLAlchemy + SQLite by default, swap in Postgres via
  `DATABASE_URL` for real scale).
- **Web frontend**: a dependency-free HTML/CSS/JS page (`backend/app/static`),
  served directly by FastAPI. No build step. Includes a login form for
  testing the API, but **not** a purchase flow — subscriptions are sold
  through the mobile apps only (App Store / Google Play require in-app
  purchase for digital subscriptions consumed in-app).
- **Mobile apps** (`mobile/`): a [Capacitor](https://capacitorjs.com) shell
  around a second, purpose-built web app (`mobile/www`) with login, a
  paywall, and native in-app purchases via
  [cordova-plugin-purchase](https://purchase.cordova.fovea.cc/). See
  `mobile/README.md`.
- **Store assets** (`store-assets/`): generated app icon, Play Store feature
  graphic, and a draft store listing (name/description/keywords/category).

## Running the backend

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd backend
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. The web page now requires signing in
(`/api/auth/signup` then `/api/auth/login`) before it will call
`/api/analyze` — this mirrors what the mobile app requires, so you can
smoke-test the whole account → subscription → analyze flow from a browser.
Since you won't have Apple/Google purchase receipts to verify locally, grant
yourself a test subscription directly in the database, e.g.:

```bash
python3 -c "
from app.db import SessionLocal
from app.models import Subscription
import datetime as dt
db = SessionLocal()
db.add(Subscription(user_id=1, platform='ios', product_id='premium_monthly',
                     external_id='dev-test-1', status='active',
                     expires_at=dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=30)))
db.commit()
"
```

API only: `GET /api/analyze?ticker=AAPL&positions=SPY,QQQ` (requires
`Authorization: Bearer <token>` from `/api/auth/login`, and an active
subscription — see "Auth, subscriptions & IAP" below).

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

## Auth, subscriptions & IAP

- `POST /api/auth/signup` / `POST /api/auth/login` — email+password, returns
  a JWT (`Authorization: Bearer <token>` on everything else).
- `GET /api/auth/me` — current user + subscription status.
- `POST /api/iap/apple/verify` — body `{"signed_transaction_info": "<JWS>"}`
  from StoreKit 2. Verifies the transaction against Apple's signature (no
  network call to Apple needed for this check) and upserts a `Subscription`
  row. Returns `503` until `APPLE_BUNDLE_ID` / `APPLE_ROOT_CERT_DIR` (and
  optionally `APPLE_APP_APPLE_ID`, `APPLE_ENVIRONMENT`) are configured.
- `POST /api/iap/google/verify` — body `{"product_id", "purchase_token"}`.
  Calls the Android Publisher API to confirm the subscription is active and
  upserts a `Subscription` row. Returns `503` until
  `GOOGLE_APPLICATION_CREDENTIALS` / `GOOGLE_PLAY_PACKAGE_NAME` are set.
- `GET /api/analyze` is gated behind `require_active_subscription` (`402` if
  none) and rate-limited to 60 req/hour/user (`429`) —
  see `backend/app/subscription.py` / `backend/app/rate_limit.py`.
- **Not implemented yet** (fine for launch, worth adding once you have
  real users): Apple App Store Server Notifications V2 and Google Real-Time
  Developer Notifications webhooks, so renewals/cancellations/refunds update
  `Subscription.status` automatically instead of only on the next app-side
  re-verify. Until then, a cancelled subscription still shows as
  active until its `expires_at` passes, which is the correct behavior anyway
  since Apple/Google don't refund the remaining period on a cancellation.

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

## Go-Live checklist

Everything above is code I could write and test myself. Everything below
requires **your** identity, payment methods, and legal agreement to Apple's
and Google's terms — I can't do any of it for you. Roughly 1-3 weeks
elapsed time (Apple review alone is typically 1-3 days but can bounce).

### 0. Business basics
- [ ] Decide legal name for the business/individual selling the app (used in
      Terms/Privacy and both consoles). Update `[YOUR LEGAL NAME OR BUSINESS
      NAME]`, `[YOUR JURISDICTION]`, `[YOUR COUNTRY]`, and `[DATE]`
      placeholders in `backend/app/static/privacy.html` and `terms.html`.
- [ ] Have a support email ready (this scaffold uses your email,
      MARCUS.TOH@gmail.com, throughout — change it in `privacy.html`,
      `terms.html`, `support.html` if you want a different address).

### 1. Apple Developer Program
- [ ] Enroll at [developer.apple.com/programs](https://developer.apple.com/programs/enroll/) — $99/year, needs a legal
      name/entity and a payment method. Individual enrollment is same-day to
      ~48h; organization enrollment needs a D-U-N-S number and can take
      longer — start this first if you're going the organization route.
- [ ] In **App Store Connect** → My Apps → **+** → New App: platform iOS,
      name "StockScanner", bundle ID `com.marcustoh.stockscanner` (register
      it under Certificates, Identifiers & Profiles first), SKU (anything
      unique, e.g. `stockscanner001`).
- [ ] **Subscriptions**: App Store Connect → your app → Monetization →
      Subscriptions → create a Subscription Group ("StockScanner
      Subscriptions") → add subscription "StockScanner Premium Monthly",
      Product ID **`premium_monthly`** (must match `mobile/www/config.js`),
      price tier that resolves to **$39.90 USD/month** in the US storefront,
      1-month duration, auto-renewing. Fill in the required localized
      display name/description and the review screenshot (a screenshot of
      the paywall screen, added once you have a build).
- [ ] **In-App Purchase key** (for server-side receipt verification): App
      Store Connect → Users and Access → Integrations → In-App Purchase →
      generate a key. Download the `.p8` file (only downloadable once!),
      note the **Key ID** and **Issuer ID**.
- [ ] **Apple root certificates** (for the same verification): download the
      certs listed at [apple.com/certificateauthority](https://www.apple.com/certificateauthority/)
      (at minimum `AppleRootCA-G3.cer`; the App Store Server library needs
      the CA chain it validates against — check
      `app-store-server-library`'s own docs for the current recommended
      set) into a directory on your server, e.g. `backend/apple_root_certs/`
      (already gitignored).
- [ ] Set these env vars on your backend host (see step 3):
      `APPLE_BUNDLE_ID=com.marcustoh.stockscanner`,
      `APPLE_ROOT_CERT_DIR=/app/backend/apple_root_certs`,
      `APPLE_ENVIRONMENT=Sandbox` (switch to `Production` once you've
      tested and are ready to go live), `APPLE_APP_APPLE_ID` (the numeric
      App ID shown in App Store Connect, needed once you flip to
      Production).

### 2. Google Play Console
- [ ] Register at [play.google.com/console](https://play.google.com/console/signup) — $25 one-time, needs a payment
      method and (for organizations) D-U-N-S verification.
- [ ] Create app → name "StockScanner" → package name
      `com.marcustoh.stockscanner` (must match `capacitor.config.json`).
- [ ] **Monetize** → Subscriptions → create product, ID **`premium_monthly`**
      → add a base plan, auto-renewing, monthly, price **$39.90 USD**
      (Google auto-converts to other storefront currencies — review before
      publishing).
- [ ] **Service account for server-side verification**: Play Console →
      Setup → API access → link a Google Cloud project → create a service
      account with the "Service Account User" role → grant it access under
      Play Console's API access page (Financial data + Manage orders) →
      create and download a JSON key.
- [ ] Set env vars on your backend host:
      `GOOGLE_APPLICATION_CREDENTIALS=/app/backend/secrets/play-service-account.json`
      (upload the JSON there — path is gitignored),
      `GOOGLE_PLAY_PACKAGE_NAME=com.marcustoh.stockscanner`.
- [ ] Complete Play Console's required Data Safety form and Content Rating
      questionnaire (answer honestly based on what this app actually
      collects — see `backend/app/static/privacy.html` for the list).

### 3. Deploy the backend
- [ ] Create a [Render](https://render.com) account (or your preferred
      Docker host — Railway/Fly.io work the same way, just skip the
      `render.yaml` blueprint and set the same env vars manually).
- [ ] New → Blueprint → connect this GitHub repo → Render reads
      `render.yaml` and provisions the service + a persistent disk for the
      SQLite file. (For real scale, swap `DATABASE_URL` for a managed
      Postgres instance instead — the code already works against either via
      SQLAlchemy.)
- [ ] Set the secret env vars in Render's dashboard: the Apple/Google ones
      from steps 1-2 (`JWT_SECRET` auto-generates itself via the blueprint).
      Upload the Apple root certs and the Google service-account JSON as a
      **Secret File** or **Disk** mount (Render supports both) rather than
      committing them to git.
- [ ] Once deployed, confirm `https://<your-service>.onrender.com/api/health`
      returns `{"status": "ok"}`.
- [ ] Update `mobile/www/config.js` → `API_BASE_URL` to that URL, and
      `ALLOWED_ORIGINS` on the backend if you also want a public web login
      page (defaults are locked to the mobile app's Capacitor origins).

### 4. Build & test the mobile apps
- [ ] Follow `mobile/README.md` end to end: `npm install`, `cap add
      ios`/`cap add android`, `cap sync`, open in Xcode/Android Studio, set
      signing/bundle ID, add the In-App Purchase capability (iOS).
- [ ] **Before submitting**: run a real purchase against Apple's Sandbox
      (TestFlight or a Sandbox tester Apple ID) and a Google Play license
      tester account, confirm `purchases.js`'s field extraction actually
      matches the live transaction shape (flagged as `TODO` in that file —
      I could not test this without a real store account), and confirm the
      backend flips your subscription to active and unlocks the app.
- [ ] Test "Restore purchases" on a fresh install.

### 5. Store listings & submission
- [ ] Use `store-assets/listing.md` for name/description/keywords/category,
      and `store-assets/icon/` + `store-assets/feature-graphic/` for the
      required images.
- [ ] Capture real screenshots from the built app (simulator or device) —
      see `listing.md` for exactly which screens/sizes each store wants.
- [ ] Fill in Privacy Policy / Terms / Support URLs pointing at your
      deployed backend's `/privacy.html`, `/terms.html`, `/support.html`.
- [ ] iOS: Xcode → Archive → upload to App Store Connect → attach the build
      to your app version → submit for review. Expect review questions
      about the "trading signal" nature of the app — the in-app disclaimers
      and `terms.html`'s "not investment advice" language are there to
      preempt that; be ready to answer Apple's reviewer notes honestly if
      they ask for clarification.
- [ ] Android: Android Studio → generate signed AAB → upload to Play
      Console's Internal Testing track first, verify the purchase flow with
      real license testers, then promote to Production.

## Disclaimer

Nothing in this app is financial advice. Options trading involves
substantial risk. Verify all data (especially IV Rank, whale activity, and
congress/insider signals, which are heuristic approximations from free data)
independently before trading.
