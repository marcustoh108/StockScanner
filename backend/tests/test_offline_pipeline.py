"""Offline smoke test: exercises indicators/options_analytics/whale/signal_engine
with synthetic data, since Yahoo Finance is unreachable from this sandbox."""
import datetime as dt

import numpy as np
import pandas as pd

from app.services.indicators import atr, compute_emas, support_resistance
from app.services.market_data import MarketSnapshot, OptionsSnapshot
from app.services import options_analytics, whale as whale_svc, signal_engine

rng = np.random.default_rng(42)
n = 300
dates = pd.date_range(end=dt.date.today(), periods=n, freq="B")
close = 150 + np.cumsum(rng.normal(0.1, 2.0, n))
high = close + rng.uniform(0.5, 2.0, n)
low = close - rng.uniform(0.5, 2.0, n)
open_ = close + rng.normal(0, 1, n)
volume = rng.integers(1_000_000, 5_000_000, n)

history = pd.DataFrame(
    {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=dates
)

spot = float(close[-1])
strikes = np.arange(round(spot * 0.8), round(spot * 1.2), 2.5)


def make_chain(strikes, spot, side):
    n_s = len(strikes)
    iv = 0.35 + rng.normal(0, 0.03, n_s)
    vol = rng.integers(10, 500, n_s)
    oi = rng.integers(50, 2000, n_s)
    mid = np.maximum(0.1, (spot - strikes) if side == "call" else (strikes - spot))
    bid = mid * 0.95
    ask = mid * 1.05 + 0.05
    df = pd.DataFrame(
        {
            "strike": strikes,
            "impliedVolatility": iv,
            "volume": vol,
            "openInterest": oi,
            "bid": bid,
            "ask": ask,
            "lastPrice": mid,
        }
    )
    # inject one whale outlier
    df.loc[df.index[len(df) // 2], "volume"] = 5000
    return df


calls = make_chain(strikes, spot, "call")
puts = make_chain(strikes, spot, "put")

exp = (dt.date.today() + dt.timedelta(days=30)).isoformat()
snap = OptionsSnapshot(expiration=exp, days_to_expiration=30, calls=calls, puts=puts)

market = MarketSnapshot(
    ticker="TEST",
    spot_price=spot,
    bid=spot - 0.05,
    ask=spot + 0.05,
    history=history,
    earnings_date=dt.date.today() + dt.timedelta(days=20),
    expirations=[exp],
    nearest_monthly=snap,
    nearest_weekly=snap,
)

emas = compute_emas(history)
atr_val = atr(history)
sr = support_resistance(history)
opt = options_analytics.build_options_analytics(market)
whale = whale_svc.build_whale_activity(market)

print("EMAs:", emas)
print("ATR:", atr_val)
print("Support/Resistance:", sr)
print("IV stats:", opt["iv"])
print("Expected move:", opt["expected_move"])
print("OI:", opt["open_interest"])
print("Earnings:", opt["earnings"])
print("Bid/Ask:", opt["bid_ask"])
print("Whale:", whale)

signal = signal_engine.evaluate(
    emas=emas,
    atr_value=atr_val,
    sr=sr,
    iv=opt["iv"],
    expected_move=opt["expected_move"],
    oi=opt["open_interest"],
    earnings=opt["earnings"],
    bid_ask=opt["bid_ask"],
    whale=whale,
    insider={"available": False},
    congress={"available": False},
    correlation={"available": False},
)
print("SIGNAL:", signal)
assert signal["recommendation"] in ("SELL PUT SPREAD", "WAIT", "AVOID")
print("OK")
