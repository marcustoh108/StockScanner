// Top-level view state machine: auth -> paywall -> main.
const views = {
  auth: document.getElementById("view-auth"),
  paywall: document.getElementById("view-paywall"),
  main: document.getElementById("view-main"),
};

function showView(name) {
  Object.entries(views).forEach(([key, el]) => {
    el.hidden = key !== name;
  });
}

// ---- Auth view ----
let authMode = "login";
const authForm = document.getElementById("auth-form");
const authTitle = document.getElementById("auth-title");
const authSubmitBtn = document.getElementById("auth-submit-btn");
const authSwitchPrompt = document.getElementById("auth-switch-prompt");
const authSwitchLink = document.getElementById("auth-switch-link");
const authError = document.getElementById("auth-error");

function setAuthMode(mode) {
  authMode = mode;
  const isLogin = mode === "login";
  authTitle.textContent = isLogin ? "Log in" : "Create your account";
  authSubmitBtn.textContent = isLogin ? "Log in" : "Sign up";
  authSwitchPrompt.textContent = isLogin ? "Don't have an account?" : "Already have an account?";
  authSwitchLink.textContent = isLogin ? "Sign up" : "Log in";
  authError.hidden = true;
}

authSwitchLink.addEventListener("click", (e) => {
  e.preventDefault();
  setAuthMode(authMode === "login" ? "signup" : "login");
});

authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  authError.hidden = true;
  const email = document.getElementById("auth-email").value.trim();
  const password = document.getElementById("auth-password").value;
  try {
    const data = authMode === "login" ? await Api.login(email, password) : await Api.signup(email, password);
    Api.setToken(data.access_token);
    await afterAuth();
  } catch (err) {
    authError.textContent = err.message;
    authError.hidden = false;
  }
});

// ---- Paywall view ----
document.getElementById("price-line").textContent = window.STOCKSCANNER_CONFIG.PRICE_DISPLAY;
document.getElementById("subscribe-price").textContent = window.STOCKSCANNER_CONFIG.PRICE_DISPLAY;

const paywallError = document.getElementById("paywall-error");

document.getElementById("subscribe-btn").addEventListener("click", () => {
  paywallError.hidden = true;
  Purchases.purchaseMonthly();
});

document.getElementById("restore-btn").addEventListener("click", () => {
  paywallError.hidden = true;
  Purchases.restore();
});

document.getElementById("paywall-logout-btn").addEventListener("click", logout);

document.querySelectorAll('[data-legal]').forEach((a) => {
  a.addEventListener("click", (e) => {
    e.preventDefault();
    const page = a.dataset.legal;
    window.open(`${window.STOCKSCANNER_CONFIG.API_BASE_URL}/${page}.html`, "_blank");
  });
});

Purchases.init({
  onEntitled: async () => {
    await afterAuth();
  },
  onError: (message) => {
    paywallError.textContent = message;
    paywallError.hidden = false;
  },
});

// ---- Main view ----
document.getElementById("logout-btn").addEventListener("click", logout);

function logout() {
  Api.setToken(null);
  setAuthMode("login");
  showView("auth");
}

async function afterAuth() {
  try {
    const me = await Api.me();
    document.getElementById("account-email").textContent = me.email;
    if (me.subscription.active) {
      showView("main");
    } else {
      showView("paywall");
    }
  } catch (err) {
    // Token invalid/expired.
    logout();
  }
}

const searchForm = document.getElementById("search-form");
const statusEl = document.getElementById("status");

function setStatus(message, isError = false) {
  statusEl.hidden = !message;
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

searchForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const ticker = document.getElementById("ticker-input").value.trim();
  if (!ticker) return;
  const positions = document.getElementById("positions-input").value.trim();

  document.getElementById("results").hidden = true;
  setStatus(`Analyzing ${ticker.toUpperCase()}…`);

  try {
    const data = await Api.analyze(ticker, positions);
    setStatus("");
    renderAnalysis(data);
  } catch (err) {
    if (err.status === 401) {
      logout();
      return;
    }
    if (err.status === 402) {
      showView("paywall");
      return;
    }
    setStatus(err.message || "Something went wrong.", true);
  }
});

// ---- Boot ----
(async function boot() {
  if (Api.getToken()) {
    await afterAuth();
  } else {
    showView("auth");
  }
})();
