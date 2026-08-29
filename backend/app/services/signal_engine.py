"""Rule-based recommendation engine: SELL PUT SPREAD / WAIT / AVOID.

This is a transparent, explainable scoring model -- not investment advice.
Each factor contributes points toward or away from "favorable conditions for
selling a put credit spread" (rich premium, defined risk, price with room
above support, no imminent binary catalyst, adequate liquidity).
"""
from __future__ import annotations

SELL = "SELL PUT SPREAD"
WAIT = "WAIT"
AVOID = "AVOID"


def _add(reasons: list[dict], score: list[float], points: float, text: str, kind: str) -> None:
    score[0] += points
    reasons.append({"text": text, "impact": kind, "points": points})


def evaluate(
    *,
    emas: dict,
    atr_value: float | None,
    sr: dict,
    iv: dict,
    expected_move: dict,
    oi: dict,
    earnings: dict,
    bid_ask: dict,
    whale: dict,
    insider: dict,
    congress: dict,
    correlation: dict,
) -> dict:
    reasons: list[dict] = []
    score = [50.0]  # start neutral, out of 0-100

    # --- IV Rank / Score: premium richness -------------------------------
    iv_rank = iv.get("iv_rank")
    iv_score = iv.get("iv_score")
    if iv_score is not None:
        if iv_score >= 60:
            _add(reasons, score, 15, f"IV Score {iv_score} is elevated -- premium looks rich.", "positive")
        elif iv_score <= 35:
            _add(reasons, score, -15, f"IV Score {iv_score} is low -- premium is thin for credit spreads.", "negative")
        else:
            _add(reasons, score, 0, f"IV Score {iv_score} is moderate.", "neutral")
    if iv_rank is not None and iv_rank < 20:
        _add(reasons, score, -8, f"IV Rank (approx.) {iv_rank}% is near yearly lows.", "negative")

    # --- Trend / EMA structure -------------------------------------------
    spot = sr.get("spot")
    ema20, ema50, ema200 = emas.get("ema20"), emas.get("ema50"), emas.get("ema200")
    if spot and ema50:
        if spot >= ema50 and (ema20 is None or ema20 >= ema50):
            _add(reasons, score, 10, "Price is at/above EMA50 with a stable-to-up trend.", "positive")
        elif spot < ema50 and ema200 and spot < ema200:
            _add(reasons, score, -15, "Price is below both EMA50 and EMA200 -- downtrend.", "negative")
        else:
            _add(reasons, score, -5, "Price is below EMA50 -- trend is shaky.", "negative")

    # --- Support/Resistance room ------------------------------------------
    nearest_support = sr.get("nearest_support")
    nearest_resistance = sr.get("nearest_resistance")
    if spot and nearest_support:
        support_room_pct = (spot - nearest_support) / spot * 100
        if support_room_pct >= 3:
            _add(reasons, score, 8, f"Price has {support_room_pct:.1f}% room above nearest support (${nearest_support:.2f}).", "positive")
        elif support_room_pct < 1:
            _add(reasons, score, -12, f"Price is sitting right on support (${nearest_support:.2f}) -- breakdown risk.", "negative")
    if spot and nearest_resistance:
        resistance_room_pct = (nearest_resistance - spot) / spot * 100
        if resistance_room_pct < 1:
            _add(reasons, score, -5, f"Price is right under resistance (${nearest_resistance:.2f}).", "negative")

    # --- Earnings proximity (hard-ish override) ---------------------------
    days_until = earnings.get("days_until_earnings")
    forced_wait = False
    if days_until is not None and 0 <= days_until <= 3:
        _add(reasons, score, -25, f"Earnings in {days_until} day(s) -- gap risk before expiration.", "negative")
        forced_wait = True
    elif days_until is not None and 4 <= days_until <= 10:
        _add(reasons, score, -8, f"Earnings in {days_until} days -- keep expirations short or size down.", "negative")
    elif days_until is not None:
        _add(reasons, score, 5, f"Earnings is {days_until} days out -- no near-term binary event.", "positive")

    # --- Expected move sanity check ---------------------------------------
    move_pct = expected_move.get("expected_move_pct")
    if move_pct is not None and move_pct >= 15:
        _add(reasons, score, -6, f"Expected move to expiration is wide ({move_pct}% of spot).", "negative")

    # --- Liquidity: bid/ask spread + OI ------------------------------------
    stock_spread = bid_ask.get("stock_spread_pct")
    option_spread = bid_ask.get("atm_option_spread_pct")
    if option_spread is not None:
        if option_spread <= 8:
            _add(reasons, score, 6, f"ATM option bid/ask spread is tight ({option_spread}%).", "positive")
        elif option_spread >= 20:
            _add(reasons, score, -12, f"ATM option bid/ask spread is wide ({option_spread}%) -- poor fill quality.", "negative")
    total_oi = oi.get("total_oi")
    if total_oi is not None:
        if total_oi >= 500:
            _add(reasons, score, 5, f"Open interest near the money is healthy ({total_oi}).", "positive")
        elif total_oi < 50:
            _add(reasons, score, -10, f"Open interest near the money is thin ({total_oi}) -- illiquid.", "negative")

    # --- Whale / unusual options activity -----------------------------------
    skew = whale.get("skew")
    if skew == "bearish":
        _add(reasons, score, -8, "Options volume skewed toward puts (bearish flow).", "negative")
    elif skew == "bullish":
        _add(reasons, score, 6, "Options volume skewed toward calls (bullish flow).", "positive")
    if whale.get("flagged_contracts"):
        n = len(whale["flagged_contracts"])
        _add(reasons, score, 0, f"{n} unusual-volume contract(s) flagged -- review before entry.", "neutral")

    # --- Insider activity -----------------------------------------------------
    if insider.get("available"):
        net = insider.get("net_value_90d", 0)
        if insider.get("buy_count_90d", 0) > 0 and net > 0:
            _add(reasons, score, 8, f"Net insider buying over 90 days (${net:,.0f}).", "positive")
        elif insider.get("sell_count_90d", 0) > insider.get("buy_count_90d", 0) and net < -1_000_000:
            _add(reasons, score, -8, f"Heavy net insider selling over 90 days (${net:,.0f}).", "negative")

    # --- Congressional activity ------------------------------------------------
    if congress.get("available") and not congress.get("stale"):
        b, s = congress.get("buy_count_180d", 0), congress.get("sell_count_180d", 0)
        if b > s and b > 0:
            _add(reasons, score, 5, f"Congress members net-bought this ticker ({b} buys vs {s} sells, 180d).", "positive")
        elif s > b and s >= 3:
            _add(reasons, score, -5, f"Congress members net-sold this ticker ({s} sells vs {b} buys, 180d).", "negative")
    elif congress.get("stale"):
        _add(reasons, score, 0, f"Congress trading data source is stale (as of {congress.get('as_of')}) -- not used in scoring.", "neutral")

    # --- Correlation / concentration risk --------------------------------------
    if correlation.get("available"):
        high = correlation.get("high_correlation_count", 0)
        if high > 0:
            _add(reasons, score, -6 * min(high, 3), f"{high} existing position(s) are highly correlated (>=0.7) -- concentration risk.", "negative")

    final_score = max(0.0, min(100.0, score[0]))

    if forced_wait:
        recommendation = WAIT
    elif final_score >= 65:
        recommendation = SELL
    elif final_score >= 40:
        recommendation = WAIT
    else:
        recommendation = AVOID

    reasons.sort(key=lambda r: r["points"])
    return {
        "recommendation": recommendation,
        "score": round(final_score, 1),
        "reasons": reasons,
    }
