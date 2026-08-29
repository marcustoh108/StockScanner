const form = document.getElementById("search-form");
const tickerInput = document.getElementById("ticker-input");
const positionsInput = document.getElementById("positions-input");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const recommendationEl = document.getElementById("recommendation");
const reasonsList = document.getElementById("reasons-list");

function fmt(value, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value}${suffix}`;
}

function fmtMoney(value) {
  if (value === null || value === undefined) return "—";
  return `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function row(dl, label, value) {
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  dl.appendChild(dt);
  dl.appendChild(dd);
}

function setStatus(message, isError = false) {
  statusEl.hidden = !message;
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function badgeClass(rec) {
  if (rec === "SELL PUT SPREAD") return "sell";
  if (rec === "WAIT") return "wait";
  return "avoid";
}

function badgeEmoji(rec) {
  if (rec === "SELL PUT SPREAD") return "🟢";
  if (rec === "WAIT") return "🟡";
  return "🔴";
}

function render(data) {
  resultsEl.hidden = false;

  const rec = data.signal.recommendation;
  recommendationEl.className = `recommendation ${badgeClass(rec)}`;
  recommendationEl.innerHTML = `${badgeEmoji(rec)} ${rec}<span class="score">Score: ${data.signal.score}/100 &middot; ${data.ticker} @ $${data.spot_price}</span>`;

  const volCard = document.getElementById("vol-card");
  volCard.innerHTML = "";
  const iv = data.options.iv_score;
  row(volCard, "IV (ATM)", iv.current_iv !== null ? `${(iv.current_iv * 100).toFixed(1)}%` : "—");
  row(volCard, "IV Rank (approx.)", fmt(iv.iv_rank, "%"));
  row(volCard, "IV Score", fmt(iv.iv_score));
  row(volCard, "HV20", iv.hv20 !== null ? `${(iv.hv20 * 100).toFixed(1)}%` : "—");
  row(volCard, "IV/HV Spread", fmt(iv.iv_hv_spread_pct, "%"));

  const techCard = document.getElementById("tech-card");
  techCard.innerHTML = "";
  const ema = data.technicals.ema;
  row(techCard, "EMA 9 / 20", `${fmt(ema.ema9 && ema.ema9.toFixed(2))} / ${fmt(ema.ema20 && ema.ema20.toFixed(2))}`);
  row(techCard, "EMA 50 / 200", `${fmt(ema.ema50 && ema.ema50.toFixed(2))} / ${fmt(ema.ema200 && ema.ema200.toFixed(2))}`);
  row(techCard, "ATR (14d)", fmtMoney(data.technicals.atr));
  const sr = data.technicals.support_resistance;
  row(techCard, "Support", (sr.support || []).map((s) => s.toFixed(2)).join(", ") || "—");
  row(techCard, "Resistance", (sr.resistance || []).map((s) => s.toFixed(2)).join(", ") || "—");

  const optCard = document.getElementById("options-card");
  optCard.innerHTML = "";
  const em = data.options.expected_move;
  row(optCard, "Expected Move", em.expected_move_dollars !== null ? `${fmtMoney(em.expected_move_dollars)} (${fmt(em.expected_move_pct, "%")})` : "—");
  row(optCard, "Move Range", em.range_low !== null ? `${fmtMoney(em.range_low)} – ${fmtMoney(em.range_high)}` : "—");
  row(optCard, "Expiration used", fmt(em.expiration));
  const oi = data.options.open_interest;
  row(optCard, "Open Interest (ATM)", fmt(oi.total_oi));
  row(optCard, "Put/Call OI Ratio", fmt(oi.put_call_oi_ratio));
  const ba = data.options.bid_ask_spread;
  row(optCard, "Stock Bid/Ask Spread", fmt(ba.stock_spread_pct, "%"));
  row(optCard, "ATM Option Spread", fmt(ba.atm_option_spread_pct, "%"));

  const earnCard = document.getElementById("earnings-card");
  earnCard.innerHTML = "";
  const earn = data.earnings;
  row(earnCard, "Earnings Date", fmt(earn.earnings_date));
  row(earnCard, "Days Until Earnings", fmt(earn.days_until_earnings));
  row(earnCard, "Within 5 Days", earn.within_5_days ? "Yes" : "No");

  const whaleCard = document.getElementById("whale-card");
  whaleCard.innerHTML = "";
  const whale = data.whale_activity;
  row(whaleCard, "Call Volume", fmt(whale.call_volume));
  row(whaleCard, "Put Volume", fmt(whale.put_volume));
  row(whaleCard, "Put/Call Vol Ratio", fmt(whale.put_call_volume_ratio));
  row(whaleCard, "Flow Skew", fmt(whale.skew));
  row(whaleCard, "Unusual Contracts", fmt(whale.flagged_contracts ? whale.flagged_contracts.length : 0));

  const insiderCard = document.getElementById("insider-card");
  insiderCard.innerHTML = "";
  const insider = data.insider_activity;
  if (insider.available) {
    row(insiderCard, "Buys (90d)", fmt(insider.buy_count_90d));
    row(insiderCard, "Sells (90d)", fmt(insider.sell_count_90d));
    row(insiderCard, "Net Value (90d)", fmtMoney(insider.net_value_90d));
  } else {
    row(insiderCard, "Status", insider.note || "Unavailable");
  }

  const congressCard = document.getElementById("congress-card");
  congressCard.innerHTML = "";
  const congress = data.congress_activity;
  if (congress.available) {
    row(congressCard, "Buys (180d)", fmt(congress.buy_count_180d));
    row(congressCard, "Sells (180d)", fmt(congress.sell_count_180d));
    row(congressCard, "Data as of", fmt(congress.as_of));
    if (congress.stale) row(congressCard, "⚠ Stale source", "yes");
  } else {
    row(congressCard, "Status", congress.note || "Unavailable");
  }

  const corrCard = document.getElementById("correlation-card");
  corrCard.innerHTML = "";
  const corr = data.correlation;
  if (corr.available && corr.correlations.length) {
    corr.correlations.forEach((c) => {
      row(corrCard, c.ticker, c.correlation !== null ? c.correlation : (c.error || "—"));
    });
  } else {
    row(corrCard, "Status", corr.note || "No positions supplied");
  }

  reasonsList.innerHTML = "";
  data.signal.reasons.forEach((r) => {
    const li = document.createElement("li");
    li.className = r.impact;
    li.textContent = r.text;
    reasonsList.appendChild(li);
  });
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const ticker = tickerInput.value.trim();
  if (!ticker) return;
  const positions = positionsInput.value.trim();

  resultsEl.hidden = true;
  setStatus(`Analyzing ${ticker.toUpperCase()}…`);

  try {
    const params = new URLSearchParams({ ticker });
    if (positions) params.set("positions", positions);
    const resp = await fetch(`/api/analyze?${params.toString()}`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${resp.status})`);
    }
    const data = await resp.json();
    setStatus("");
    render(data);
  } catch (err) {
    setStatus(err.message || "Something went wrong.", true);
  }
});
