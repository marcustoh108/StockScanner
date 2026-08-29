// Thin wrapper around the StockScanner backend API.
const API_BASE = window.STOCKSCANNER_CONFIG.API_BASE_URL;
const TOKEN_KEY = "stockscanner_token";

const Api = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },
  setToken(token) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  },

  async _json(path, options = {}) {
    const resp = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(this.getToken() ? { Authorization: `Bearer ${this.getToken()}` } : {}),
        ...(options.headers || {}),
      },
    });
    let data = null;
    try {
      data = await resp.json();
    } catch {
      // no body
    }
    if (!resp.ok) {
      const err = new Error((data && data.detail) || `Request failed (${resp.status})`);
      err.status = resp.status;
      throw err;
    }
    return data;
  },

  signup(email, password) {
    return this._json("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) });
  },
  login(email, password) {
    return this._json("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
  },
  me() {
    return this._json("/api/auth/me");
  },
  analyze(ticker, positions) {
    const params = new URLSearchParams({ ticker });
    if (positions) params.set("positions", positions);
    return this._json(`/api/analyze?${params.toString()}`);
  },
  verifyApple(signedTransactionInfo) {
    return this._json("/api/iap/apple/verify", {
      method: "POST",
      body: JSON.stringify({ signed_transaction_info: signedTransactionInfo }),
    });
  },
  verifyGoogle(productId, purchaseToken) {
    return this._json("/api/iap/google/verify", {
      method: "POST",
      body: JSON.stringify({ product_id: productId, purchase_token: purchaseToken }),
    });
  },
};
