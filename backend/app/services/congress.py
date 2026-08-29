"""Congressional trading disclosures via House Stock Watcher / Senate Stock
Watcher public data dumps (no API key required).

These community-maintained data dumps are not guaranteed to be current -- the
free "stock watcher" projects have a history of going stale or disappearing.
We explicitly detect staleness (based on the newest transaction date present
in the fetched data) and surface it rather than silently reporting "no
activity" when the real answer is "the data source is out of date."
"""
from __future__ import annotations

import datetime as dt

import requests

from app.config import HOUSE_STOCK_WATCHER_URL, HTTP_USER_AGENT, SENATE_STOCK_WATCHER_URL
from app.services.cache import cached

_DUMP_TIMEOUT = 20
_STALE_AFTER_DAYS = 45
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y")


def _parse_date(date_str: str | None) -> dt.date | None:
    if not date_str:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _fetch_json(url: str) -> list[dict]:
    resp = requests.get(url, timeout=_DUMP_TIMEOUT, headers={"User-Agent": HTTP_USER_AGENT})
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        # Some endpoints wrap the list, e.g. {"results": [...]} or {"data": [...]}.
        for key in ("results", "data", "transactions"):
            if isinstance(data.get(key), list):
                return data[key]
        return []
    return data if isinstance(data, list) else []


def _load_house() -> list[dict]:
    try:
        return _fetch_json(HOUSE_STOCK_WATCHER_URL)
    except Exception:
        return []


def _load_senate() -> list[dict]:
    try:
        return _fetch_json(SENATE_STOCK_WATCHER_URL)
    except Exception:
        return []


def _cached_house() -> list[dict]:
    return cached("congress:house:all", ttl=3600)(_load_house)


def _cached_senate() -> list[dict]:
    return cached("congress:senate:all", ttl=3600)(_load_senate)


def _classify_type(t: str) -> str:
    t = (t or "").lower()
    if "purchase" in t:
        return "buy"
    if "sale" in t:
        return "sell"
    return "other"


def fetch_congress_activity(ticker: str) -> dict:
    ticker = ticker.strip().upper()

    def _load() -> dict:
        house = _cached_house()
        senate = _cached_senate()

        if not house and not senate:
            return {
                "available": False,
                "stale": None,
                "as_of": None,
                "buy_count_180d": 0,
                "sell_count_180d": 0,
                "recent_transactions": [],
                "note": "Congressional trading data unavailable right now.",
            }

        all_rows = []
        for row in house:
            tx_date = _parse_date(row.get("transaction_date") or row.get("disclosure_date"))
            all_rows.append(
                {
                    "chamber": "House",
                    "member": row.get("representative"),
                    "ticker": (row.get("ticker") or "").upper(),
                    "date": tx_date,
                    "type": _classify_type(row.get("type")),
                    "amount": row.get("amount"),
                }
            )
        for row in senate:
            tx_date = _parse_date(row.get("transaction_date"))
            all_rows.append(
                {
                    "chamber": "Senate",
                    "member": row.get("senator"),
                    "ticker": (row.get("ticker") or "").upper(),
                    "date": tx_date,
                    "type": _classify_type(row.get("type")),
                    "amount": row.get("amount"),
                }
            )

        dated_rows = [r for r in all_rows if r["date"] is not None]
        as_of = max((r["date"] for r in dated_rows), default=None)
        is_stale = as_of is not None and (dt.date.today() - as_of).days > _STALE_AFTER_DAYS

        # Use a window relative to the freshest data actually available, so a
        # stale dump still yields a meaningful "most recent known" signal
        # instead of always reporting zero activity.
        window_end = as_of or dt.date.today()
        cutoff = window_end - dt.timedelta(days=180)

        matches = [
            r for r in dated_rows if r["ticker"] == ticker and cutoff <= r["date"] <= window_end
        ]
        buy_count = sum(1 for r in matches if r["type"] == "buy")
        sell_count = sum(1 for r in matches if r["type"] == "sell")
        matches.sort(key=lambda r: r["date"], reverse=True)

        note = "Source: House Stock Watcher / Senate Stock Watcher public disclosure data."
        if is_stale:
            note += f" WARNING: newest record on file is from {as_of.isoformat()} -- this source appears stale."

        return {
            "available": True,
            "stale": is_stale,
            "as_of": as_of.isoformat() if as_of else None,
            "buy_count_180d": buy_count,
            "sell_count_180d": sell_count,
            "recent_transactions": [
                {
                    "chamber": r["chamber"],
                    "member": r["member"],
                    "date": r["date"].isoformat(),
                    "type": r["type"],
                    "amount": r["amount"],
                }
                for r in matches[:8]
            ],
            "note": note,
        }

    return cached(f"congress:{ticker}", ttl=3600)(_load)
