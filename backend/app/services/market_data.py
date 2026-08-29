"""Market data access via yfinance: price history, options chains, earnings."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

from app.services.cache import cached


class TickerNotFoundError(Exception):
    pass


@dataclass
class OptionsSnapshot:
    expiration: str
    days_to_expiration: int
    calls: pd.DataFrame
    puts: pd.DataFrame


@dataclass
class MarketSnapshot:
    ticker: str
    spot_price: float
    bid: float | None
    ask: float | None
    history: pd.DataFrame  # daily OHLCV, ~2y
    earnings_date: dt.date | None
    expirations: list[str] = field(default_factory=list)
    nearest_monthly: OptionsSnapshot | None = None
    nearest_weekly: OptionsSnapshot | None = None


def _fetch_history(tk: yf.Ticker) -> pd.DataFrame:
    hist = tk.history(period="2y", interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        raise TickerNotFoundError("No price history returned")
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    return hist


def _fetch_earnings_date(tk: yf.Ticker) -> dt.date | None:
    try:
        edf = tk.get_earnings_dates(limit=8)
        if edf is not None and not edf.empty:
            today = pd.Timestamp.now(tz=edf.index.tz) if edf.index.tz else pd.Timestamp.now()
            future = edf[edf.index >= today - pd.Timedelta(days=1)]
            target = future.index[-1] if not future.empty else edf.index[0]
            return pd.Timestamp(target).date()
    except Exception:
        pass
    try:
        cal = tk.calendar
        if isinstance(cal, dict) and cal.get("Earnings Date"):
            val = cal["Earnings Date"]
            d = val[0] if isinstance(val, (list, tuple)) else val
            if isinstance(d, dt.date):
                return d
        elif hasattr(cal, "empty") and not cal.empty and "Earnings Date" in getattr(cal, "index", []):
            d = cal.loc["Earnings Date"][0]
            if isinstance(d, dt.date):
                return d
    except Exception:
        pass
    return None


def _nearest_expiration(expirations: list[str], min_days: int, max_days: int) -> str | None:
    today = dt.date.today()
    candidates = []
    for exp in expirations:
        try:
            exp_date = dt.datetime.strptime(exp, "%Y-%m-%d").date()
        except ValueError:
            continue
        days = (exp_date - today).days
        if min_days <= days <= max_days:
            candidates.append((days, exp))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


def _fetch_options_snapshot(tk: yf.Ticker, expiration: str) -> OptionsSnapshot | None:
    try:
        chain = tk.option_chain(expiration)
    except Exception:
        return None
    days = (dt.datetime.strptime(expiration, "%Y-%m-%d").date() - dt.date.today()).days
    return OptionsSnapshot(
        expiration=expiration,
        days_to_expiration=max(days, 0),
        calls=chain.calls,
        puts=chain.puts,
    )


def get_market_snapshot(ticker: str) -> MarketSnapshot:
    ticker = ticker.strip().upper()

    def _load() -> MarketSnapshot:
        tk = yf.Ticker(ticker)
        history = _fetch_history(tk)
        spot_price = float(history["Close"].iloc[-1])

        bid = ask = None
        try:
            fi = tk.fast_info
            bid = float(fi.get("bid")) if fi.get("bid") else None
            ask = float(fi.get("ask")) if fi.get("ask") else None
        except Exception:
            pass
        if not bid or not ask:
            try:
                info = tk.info
                bid = bid or info.get("bid")
                ask = ask or info.get("ask")
            except Exception:
                pass

        earnings_date = _fetch_earnings_date(tk)

        expirations = list(tk.options) if tk.options else []
        nearest_weekly = None
        nearest_monthly = None
        if expirations:
            weekly_exp = _nearest_expiration(expirations, 0, 45) or expirations[0]
            nearest_weekly = _fetch_options_snapshot(tk, weekly_exp)
            monthly_exp = _nearest_expiration(expirations, 25, 60) or (
                expirations[min(1, len(expirations) - 1)]
            )
            nearest_monthly = _fetch_options_snapshot(tk, monthly_exp)

        return MarketSnapshot(
            ticker=ticker,
            spot_price=spot_price,
            bid=bid,
            ask=ask,
            history=history,
            earnings_date=earnings_date,
            expirations=expirations,
            nearest_monthly=nearest_monthly,
            nearest_weekly=nearest_weekly,
        )

    return cached(f"snapshot:{ticker}", ttl=300)(_load)


def get_price_history(ticker: str) -> pd.DataFrame:
    ticker = ticker.strip().upper()

    def _load() -> pd.DataFrame:
        tk = yf.Ticker(ticker)
        return _fetch_history(tk)

    return cached(f"history:{ticker}", ttl=900)(_load)
