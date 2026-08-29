"""Return correlation of the target ticker vs a user-supplied list of existing positions."""
from __future__ import annotations

import pandas as pd

from app.services.market_data import TickerNotFoundError, get_price_history


def compute_correlations(ticker: str, positions: list[str], lookback_days: int = 180) -> dict:
    positions = [p.strip().upper() for p in positions if p.strip()]
    positions = [p for p in positions if p != ticker.upper()]
    if not positions:
        return {"available": False, "correlations": [], "note": "No comparison positions supplied."}

    try:
        target_hist = get_price_history(ticker)
    except TickerNotFoundError:
        return {"available": False, "correlations": [], "note": "Target ticker price history unavailable."}

    target_returns = target_hist["Close"].pct_change().tail(lookback_days)

    results = []
    for pos in positions:
        try:
            pos_hist = get_price_history(pos)
        except Exception:
            results.append({"ticker": pos, "correlation": None, "error": "unavailable"})
            continue
        pos_returns = pos_hist["Close"].pct_change().tail(lookback_days)
        joined = pd.concat([target_returns, pos_returns], axis=1, join="inner").dropna()
        if len(joined) < 20:
            results.append({"ticker": pos, "correlation": None, "error": "insufficient overlap"})
            continue
        corr = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
        results.append({"ticker": pos, "correlation": round(corr, 2)})

    high_corr = [r for r in results if r.get("correlation") is not None and r["correlation"] >= 0.7]

    return {
        "available": True,
        "correlations": results,
        "high_correlation_count": len(high_corr),
        "note": "Pearson correlation of daily returns over the trailing ~6 months.",
    }
