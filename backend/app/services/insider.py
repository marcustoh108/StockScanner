"""Insider buying/selling via openinsider.com (public aggregator of SEC Form 4 filings)."""
from __future__ import annotations

import io

import pandas as pd
import requests

from app.config import HTTP_USER_AGENT, OPENINSIDER_URL, REQUEST_TIMEOUT
from app.services.cache import cached


def _empty_result(note: str) -> dict:
    return {
        "available": False,
        "buy_count_90d": 0,
        "sell_count_90d": 0,
        "buy_value_90d": 0,
        "sell_value_90d": 0,
        "net_value_90d": 0,
        "recent_transactions": [],
        "note": note,
    }


def _parse_openinsider_table(html: str) -> pd.DataFrame | None:
    try:
        tables = pd.read_html(io.StringIO(html))
    except Exception:
        return None
    for t in tables:
        cols = [str(c) for c in t.columns]
        if any("Trade Type" in c or "Insider Name" in c for c in cols):
            return t
    return None


def fetch_insider_activity(ticker: str) -> dict:
    ticker = ticker.strip().upper()

    def _load() -> dict:
        url = OPENINSIDER_URL.format(ticker=ticker)
        try:
            resp = requests.get(
                url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": HTTP_USER_AGENT}
            )
            resp.raise_for_status()
        except Exception as exc:  # network/blocked/etc.
            return _empty_result(f"Insider data unavailable ({exc.__class__.__name__}).")

        table = _parse_openinsider_table(resp.text)
        if table is None or table.empty:
            return _empty_result("No recent insider filings found.")

        table = table.rename(columns=lambda c: str(c).strip())
        type_col = next((c for c in table.columns if "Trade Type" in c), None)
        value_col = next((c for c in table.columns if c.strip() == "Value"), None)
        qty_col = next((c for c in table.columns if "Qty" in c and "Owned" not in c), None)
        insider_col = next((c for c in table.columns if "Insider Name" in c), None)
        title_col = next((c for c in table.columns if c.strip() == "Title"), None)
        date_col = next((c for c in table.columns if "Trade Date" in c), None)
        price_col = next((c for c in table.columns if c.strip() == "Price"), None)

        def to_num(series: pd.Series) -> pd.Series:
            return pd.to_numeric(
                series.astype(str).str.replace(r"[$,+]", "", regex=True), errors="coerce"
            )

        if value_col:
            table["_value"] = to_num(table[value_col]).fillna(0)
        else:
            table["_value"] = 0

        is_buy = table[type_col].astype(str).str.contains("P - Purchase", na=False) if type_col else pd.Series([False] * len(table))
        is_sell = table[type_col].astype(str).str.contains("S - Sale", na=False) if type_col else pd.Series([False] * len(table))

        buys = table[is_buy]
        sells = table[is_sell]
        buy_value = float(buys["_value"].abs().sum())
        sell_value = float(sells["_value"].abs().sum())

        recent = []
        for _, row in table.head(8).iterrows():
            recent.append(
                {
                    "date": str(row.get(date_col, "")) if date_col else None,
                    "insider": str(row.get(insider_col, "")) if insider_col else None,
                    "title": str(row.get(title_col, "")) if title_col else None,
                    "trade_type": str(row.get(type_col, "")) if type_col else None,
                    "price": str(row.get(price_col, "")) if price_col else None,
                    "qty": str(row.get(qty_col, "")) if qty_col else None,
                    "value": str(row.get(value_col, "")) if value_col else None,
                }
            )

        return {
            "available": True,
            "buy_count_90d": int(is_buy.sum()),
            "sell_count_90d": int(is_sell.sum()),
            "buy_value_90d": round(buy_value, 2),
            "sell_value_90d": round(sell_value, 2),
            "net_value_90d": round(buy_value - sell_value, 2),
            "recent_transactions": recent,
            "note": "Source: openinsider.com (public aggregator of SEC Form 4 filings).",
        }

    return cached(f"insider:{ticker}", ttl=1800)(_load)
