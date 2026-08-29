from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.models import User
from app.rate_limit import rate_limited_user
from app.routers.auth_router import router as auth_router
from app.routers.iap_router import router as iap_router
from app.services import correlation as correlation_svc
from app.services import congress as congress_svc
from app.services import insider as insider_svc
from app.services import options_analytics
from app.services import signal_engine
from app.services import whale as whale_svc
from app.services.indicators import atr, compute_emas, support_resistance
from app.services.market_data import TickerNotFoundError, get_market_snapshot
from app.subscription import require_active_subscription

app = FastAPI(title="StockScanner API", version="1.0.0")


@app.on_event("startup")
def _startup() -> None:
    init_db()


_default_origins = (
    "capacitor://localhost,ionic://localhost,http://localhost,https://localhost"
)
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(iap_router)

_executor = ThreadPoolExecutor(max_workers=8)

DISCLAIMER = (
    "Informational and educational only -- not investment advice. Data comes "
    "from free/public sources and may be delayed, approximate, or unavailable "
    "for some tickers. Options trading involves substantial risk; verify "
    "everything independently before trading."
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/analyze")
def analyze(
    ticker: str = Query(..., min_length=1, max_length=10),
    positions: str = Query("", description="Comma-separated list of existing position tickers"),
    user: User = Depends(require_active_subscription),
    _rl: User = Depends(rate_limited_user),
) -> dict:
    ticker = ticker.strip().upper()
    if not all(c.isalnum() or c in ".-" for c in ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    try:
        snapshot = get_market_snapshot(ticker)
    except TickerNotFoundError:
        raise HTTPException(status_code=404, detail=f"No market data found for '{ticker}'")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch market data: {exc}")

    position_list = [p for p in positions.split(",") if p.strip()]

    insider_future = _executor.submit(insider_svc.fetch_insider_activity, ticker)
    congress_future = _executor.submit(congress_svc.fetch_congress_activity, ticker)
    correlation_future = _executor.submit(correlation_svc.compute_correlations, ticker, position_list)

    emas = compute_emas(snapshot.history)
    atr_value = atr(snapshot.history)
    sr = support_resistance(snapshot.history)
    opt_analytics = options_analytics.build_options_analytics(snapshot)
    whale = whale_svc.build_whale_activity(snapshot)

    insider = insider_future.result()
    congress = congress_future.result()
    correlation = correlation_future.result()

    signal = signal_engine.evaluate(
        emas=emas,
        atr_value=atr_value,
        sr=sr,
        iv=opt_analytics["iv"],
        expected_move=opt_analytics["expected_move"],
        oi=opt_analytics["open_interest"],
        earnings=opt_analytics["earnings"],
        bid_ask=opt_analytics["bid_ask"],
        whale=whale,
        insider=insider,
        congress=congress,
        correlation=correlation,
    )

    return {
        "ticker": ticker,
        "spot_price": opt_analytics["spot_price"],
        "technicals": {
            "ema": emas,
            "atr": round(atr_value, 2) if atr_value is not None else None,
            "support_resistance": sr,
        },
        "options": {
            "iv_score": opt_analytics["iv"],
            "expected_move": opt_analytics["expected_move"],
            "open_interest": opt_analytics["open_interest"],
            "bid_ask_spread": opt_analytics["bid_ask"],
        },
        "earnings": opt_analytics["earnings"],
        "whale_activity": whale,
        "insider_activity": insider,
        "congress_activity": congress,
        "correlation": correlation,
        "signal": signal,
        "disclaimer": DISCLAIMER,
    }


_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
