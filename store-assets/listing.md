# App Store / Google Play listing draft

Copy-paste starting point for both consoles. Character limits noted per
field; trim/adjust in-console since exact limits shift occasionally.

## App name
**StockScanner** (App Store: "Name" field, 30 char max — fits. Google Play: "App name", 30 char max — fits.)

## Subtitle / short description
- **App Store subtitle** (30 chars max): `Options premium scanner`
- **Google Play short description** (80 chars max): `IV rank, EMA, whale & insider signals for options premium-selling trades.`

## Full description

```
StockScanner turns one ticker into a complete options premium-selling
research workup — in seconds.

Enter any ticker and get:
• IV Score & IV Rank (volatility-richness read)
• EMA (9/20/50/200) and trend structure
• Support & resistance levels
• Next earnings date and days-to-earnings
• ATR and expected move to expiration
• Bid/ask spreads (stock and at-the-money options) and open interest
• Whale activity — unusual options volume detection
• Insider buying (SEC Form 4 filings)
• Congressional trading activity
• Correlation to your existing positions

Every metric rolls up into one clear call:
🟢 SELL PUT SPREAD — 🟡 WAIT — 🔴 AVOID
— with the full, plain-English reasoning behind it, not just a black-box
score.

StockScanner Premium is $39.90/month. Cancel anytime in your App Store or
Google Play account settings.

IMPORTANT: StockScanner is an informational and educational research tool.
It is not investment advice and we are not a registered investment adviser
or broker-dealer. Market data comes from free/public sources and may be
delayed or approximate. Options trading carries substantial risk — verify
everything independently and consult a licensed professional before
trading. See full disclaimers in the app.
```

## Keywords (App Store, 100 chars, comma-separated, no spaces needed to save chars)
```
options,iv rank,implied volatility,put spread,credit spread,earnings,whale activity,insider trading,congress trades,ema,atr
```

## Google Play category / App Store primary category
**Finance** (both stores). Consider **Business** as a secondary category on
the App Store if Finance review is unusually strict about "signals" apps —
decide after reading Apple's response, if any, during review.

## Age rating
- App Store: 17+ (Unrestricted Web Access is not applicable, but
  "Infrequent/Mild Simulated Gambling" and financial-risk content questions
  in the questionnaire should be answered honestly — a "trading tool"
  answer set typically lands at 17+).
- Google Play: rate via the Content Rating questionnaire; a finance/trading
  utility with no gambling mechanic typically lands in "Everyone" or "Teen"
  — answer the questionnaire honestly rather than assuming.

## Screenshots needed (capture from a real device/simulator once built)
1. Main analyze screen with a populated result (pick a liquid, well-known
   ticker so all cards populate).
2. The recommendation badge close-up (🟢/🟡/🔴) with the "why" reasons list.
3. Paywall/subscribe screen.
4. A card-detail view (e.g. Whale Activity or IV Score) if screen space
   allows a zoomed shot.
- iOS sizes needed: 6.9" (1320x2868 or current required size — check current
  Apple spec at submission time, sizes are periodically bumped), 6.5", and
  iPad if you support it.
- Android: at minimum 2 phone screenshots, 16:9 or 9:16, 320–3840px per
  side.

## Support / marketing URLs (once backend is deployed)
- Privacy Policy: `https://<your-backend-domain>/privacy.html`
- Terms of Service: `https://<your-backend-domain>/terms.html`
- Support URL: `https://<your-backend-domain>/support.html`
- Marketing URL (optional): same as support, or a dedicated landing page.

## In-app purchase / subscription listing (in-console, not the app binary)
- Reference name: `StockScanner Premium Monthly`
- Product ID: `premium_monthly` (must match `mobile/www/config.js` →
  `MONTHLY_PRODUCT_ID` exactly on both platforms)
- Price: **$39.90 USD / month**, auto-renewing. Apple/Google will localize
  this to other storefronts' currencies automatically using their own
  price-tier conversion — review the generated local prices before
  publishing if exact parity matters to you.
- Subscription group (App Store): create one group, e.g. "StockScanner
  Subscriptions", with this as the single tier for now.
- Free trial / intro offer: optional — decide separately, not included in
  this scaffold.
