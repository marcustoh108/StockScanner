"""Options-derived analytics: ATM IV, IV Rank/Score, expected move, spreads, OI."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from app.services.indicators import realized_volatility
from app.services.market_data import MarketSnapshot, OptionsSnapshot


def _atm_rows(df: pd.DataFrame, spot: float, n: int = 3) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    d = df.copy()
    d["dist"] = (d["strike"] - spot).abs()
    return d.sort_values("dist").head(n)


def atm_implied_vol(snap: OptionsSnapshot, spot: float) -> float | None:
    if snap is None:
        return None
    ivs = []
    for df in (snap.calls, snap.puts):
        atm = _atm_rows(df, spot, n=1)
        if not atm.empty and "impliedVolatility" in atm:
            iv = atm["impliedVolatility"].iloc[0]
            if iv and iv > 0:
                ivs.append(float(iv))
    if not ivs:
        return None
    return float(np.mean(ivs))


def atm_straddle_price(snap: OptionsSnapshot, spot: float) -> float | None:
    if snap is None:
        return None
    call_atm = _atm_rows(snap.calls, spot, n=1)
    put_atm = _atm_rows(snap.puts, spot, n=1)
    if call_atm.empty or put_atm.empty:
        return None

    def mid(row) -> float | None:
        bid, ask, last = row.get("bid"), row.get("ask"), row.get("lastPrice")
        if bid and ask and bid > 0 and ask > 0:
            return (bid + ask) / 2
        return float(last) if last else None

    c_mid = mid(call_atm.iloc[0])
    p_mid = mid(put_atm.iloc[0])
    if c_mid is None or p_mid is None:
        return None
    return float(c_mid + p_mid)


def open_interest_summary(snap: OptionsSnapshot, spot: float) -> dict:
    if snap is None:
        return {"call_oi": None, "put_oi": None, "total_oi": None, "put_call_oi_ratio": None}
    call_atm = _atm_rows(snap.calls, spot, n=3)
    put_atm = _atm_rows(snap.puts, spot, n=3)
    call_oi = int(call_atm["openInterest"].fillna(0).sum()) if not call_atm.empty else 0
    put_oi = int(put_atm["openInterest"].fillna(0).sum()) if not put_atm.empty else 0
    total = call_oi + put_oi
    return {
        "call_oi": call_oi,
        "put_oi": put_oi,
        "total_oi": total,
        "put_call_oi_ratio": round(put_oi / call_oi, 2) if call_oi else None,
    }


def atm_option_spread_pct(snap: OptionsSnapshot, spot: float) -> float | None:
    """Average bid/ask spread % across ATM call & put (liquidity proxy)."""
    if snap is None:
        return None
    pct_list = []
    for df in (snap.calls, snap.puts):
        atm = _atm_rows(df, spot, n=1)
        if atm.empty:
            continue
        row = atm.iloc[0]
        bid, ask = row.get("bid"), row.get("ask")
        if bid and ask and (bid + ask) > 0:
            pct_list.append((ask - bid) / ((ask + bid) / 2) * 100)
    if not pct_list:
        return None
    return float(np.mean(pct_list))


def iv_rank_and_score(current_iv: float | None, history: pd.DataFrame) -> dict:
    """IV Rank/Score approximation.

    True IV Rank needs a 52-week history of implied volatility, which isn't
    available from free data sources. We approximate the *range* IV has likely
    occupied using trailing 252-day realized volatility (HV20) as a proxy
    distribution, and separately report the IV/HV spread ("richness") which is
    a standard signal for premium-selling attractiveness.
    """
    result = {
        "current_iv": current_iv,
        "hv20": None,
        "iv_rank": None,
        "iv_hv_spread_pct": None,
        "iv_score": None,
        "note": "IV Rank is an approximation using trailing realized-volatility "
        "range as a proxy for the unavailable historical IV series.",
    }
    if current_iv is None:
        return result

    hv_series = realized_volatility(history, window=20).dropna().tail(252)
    hv20_latest = float(hv_series.iloc[-1]) if not hv_series.empty else None
    result["hv20"] = hv20_latest

    if not hv_series.empty:
        hv_min, hv_max = float(hv_series.min()), float(hv_series.max())
        if hv_max > hv_min:
            iv_rank = (current_iv - hv_min) / (hv_max - hv_min) * 100
            result["iv_rank"] = round(float(np.clip(iv_rank, 0, 100)), 1)

    if hv20_latest and hv20_latest > 0:
        spread_pct = (current_iv - hv20_latest) / hv20_latest * 100
        result["iv_hv_spread_pct"] = round(spread_pct, 1)

    iv_rank_component = result["iv_rank"] if result["iv_rank"] is not None else 50.0
    spread = result["iv_hv_spread_pct"] if result["iv_hv_spread_pct"] is not None else 0.0
    spread_component = float(np.clip(50 + spread, 0, 100))
    iv_score = 0.6 * iv_rank_component + 0.4 * spread_component
    result["iv_score"] = round(float(np.clip(iv_score, 0, 100)), 1)
    return result


def expected_move(snap: OptionsSnapshot, spot: float, atm_iv: float | None) -> dict:
    """Expected move to expiration via ATM straddle price (primary) and the
    IV*sqrt(t) formula (fallback/cross-check)."""
    straddle = atm_straddle_price(snap, spot) if snap else None
    dte = snap.days_to_expiration if snap else None

    straddle_move = straddle * 0.85 if straddle else None  # standard 1-SD approximation
    formula_move = None
    if atm_iv and dte is not None and dte >= 0:
        formula_move = spot * atm_iv * np.sqrt(dte / 365)

    move = straddle_move if straddle_move is not None else formula_move
    return {
        "expiration": snap.expiration if snap else None,
        "days_to_expiration": dte,
        "expected_move_dollars": round(move, 2) if move is not None else None,
        "expected_move_pct": round(move / spot * 100, 2) if move is not None and spot else None,
        "range_low": round(spot - move, 2) if move is not None else None,
        "range_high": round(spot + move, 2) if move is not None else None,
        "method": "atm_straddle" if straddle_move is not None else (
            "iv_formula" if formula_move is not None else None
        ),
    }


def earnings_distance(earnings_date: dt.date | None) -> dict:
    if earnings_date is None:
        return {"earnings_date": None, "days_until_earnings": None, "within_5_days": False}
    days = (earnings_date - dt.date.today()).days
    return {
        "earnings_date": earnings_date.isoformat(),
        "days_until_earnings": days,
        "within_5_days": 0 <= days <= 5,
    }


def stock_bid_ask_spread_pct(snapshot: MarketSnapshot) -> float | None:
    if not snapshot.bid or not snapshot.ask or (snapshot.bid + snapshot.ask) <= 0:
        return None
    return float((snapshot.ask - snapshot.bid) / ((snapshot.ask + snapshot.bid) / 2) * 100)


def build_options_analytics(snapshot: MarketSnapshot) -> dict:
    spot = snapshot.spot_price
    monthly = snapshot.nearest_monthly
    atm_iv = atm_implied_vol(monthly, spot) if monthly else None
    if atm_iv is None and snapshot.nearest_weekly:
        atm_iv = atm_implied_vol(snapshot.nearest_weekly, spot)

    iv_stats = iv_rank_and_score(atm_iv, snapshot.history)
    exp_move = expected_move(monthly or snapshot.nearest_weekly, spot, atm_iv)
    oi = open_interest_summary(monthly or snapshot.nearest_weekly, spot)
    earn_dist = earnings_distance(snapshot.earnings_date)

    option_spread_pct = atm_option_spread_pct(monthly or snapshot.nearest_weekly, spot)
    stock_spread_pct = stock_bid_ask_spread_pct(snapshot)

    return {
        "spot_price": round(spot, 2),
        "iv": iv_stats,
        "expected_move": exp_move,
        "open_interest": oi,
        "earnings": earn_dist,
        "bid_ask": {
            "stock_spread_pct": round(stock_spread_pct, 3) if stock_spread_pct is not None else None,
            "atm_option_spread_pct": round(option_spread_pct, 2) if option_spread_pct is not None else None,
        },
    }
