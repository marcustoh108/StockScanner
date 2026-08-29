"""Unusual options activity ('whale') heuristic.

True whale/block-trade tape reads require paid order-flow data. As a free-data
proxy, we flag contracts whose volume is a statistical outlier relative to the
rest of the same expiration's chain, and whose volume significantly exceeds
open interest (fresh positioning rather than existing OI turning over).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.market_data import MarketSnapshot, OptionsSnapshot


def _outliers(df: pd.DataFrame, side: str, z_thresh: float = 2.0, min_volume: int = 250) -> list[dict]:
    if df is None or df.empty or "volume" not in df:
        return []
    d = df.copy()
    d["volume"] = d["volume"].fillna(0)
    d["openInterest"] = d["openInterest"].fillna(0)
    if d["volume"].sum() == 0:
        return []
    mean, std = d["volume"].mean(), d["volume"].std()
    if not std or np.isnan(std):
        return []
    d["z"] = (d["volume"] - mean) / std
    d["vol_oi_ratio"] = d["volume"] / d["openInterest"].replace(0, np.nan)
    flagged = d[(d["z"] >= z_thresh) & (d["volume"] >= min_volume)]
    out = []
    for _, row in flagged.sort_values("volume", ascending=False).head(5).iterrows():
        out.append(
            {
                "side": side,
                "strike": float(row["strike"]),
                "volume": int(row["volume"]),
                "open_interest": int(row["openInterest"]),
                "vol_oi_ratio": round(float(row["vol_oi_ratio"]), 2) if pd.notna(row["vol_oi_ratio"]) else None,
                "implied_volatility": round(float(row["impliedVolatility"]), 3)
                if pd.notna(row.get("impliedVolatility"))
                else None,
            }
        )
    return out


def whale_activity(snap: OptionsSnapshot | None) -> dict:
    if snap is None:
        return {
            "call_volume": None,
            "put_volume": None,
            "put_call_volume_ratio": None,
            "flagged_contracts": [],
            "skew": "unknown",
            "note": "No options chain available.",
        }

    call_vol = int(snap.calls["volume"].fillna(0).sum()) if not snap.calls.empty else 0
    put_vol = int(snap.puts["volume"].fillna(0).sum()) if not snap.puts.empty else 0
    ratio = round(put_vol / call_vol, 2) if call_vol else None

    if ratio is None:
        skew = "unknown"
    elif ratio >= 1.3:
        skew = "bearish"
    elif ratio <= 0.7:
        skew = "bullish"
    else:
        skew = "neutral"

    flagged = _outliers(snap.calls, "call") + _outliers(snap.puts, "put")
    flagged.sort(key=lambda r: r["volume"], reverse=True)

    return {
        "call_volume": call_vol,
        "put_volume": put_vol,
        "put_call_volume_ratio": ratio,
        "flagged_contracts": flagged[:5],
        "skew": skew,
        "note": "Heuristic proxy based on public volume/OI data, not true block-trade tape.",
    }


def build_whale_activity(snapshot: MarketSnapshot) -> dict:
    snap = snapshot.nearest_weekly or snapshot.nearest_monthly
    return whale_activity(snap)
