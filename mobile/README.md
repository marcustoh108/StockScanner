# StockScanner mobile (Capacitor)

A native iOS/Android shell around the StockScanner backend, using
[Capacitor](https://capacitorjs.com) to wrap the `www/` web app and
[cordova-plugin-purchase](https://purchase.cordova.fovea.cc/) for in-app
subscriptions on both the App Store and Google Play.

This can only be built and submitted from your own machine — iOS builds
require Xcode (macOS only) and code signing tied to your Apple Developer
account; Android builds require Android Studio / the Android SDK. Neither is
available in the sandbox this scaffold was generated in, so **none of this
has been build-tested end to end** — `npm install` and `npx cap sync` were
verified to run cleanly, but the native projects, the purchase flow, and the
store builds themselves need to be done and tested by you.

## 1. Point it at your deployed backend

Edit `www/config.js`:

```js
window.STOCKSCANNER_CONFIG = {
  API_BASE_URL: "https://your-backend.example.com", // no trailing slash
  MONTHLY_PRODUCT_ID: "premium_monthly",
  PRICE_DISPLAY: "$39.90/month",
};
```

`MONTHLY_PRODUCT_ID` must exactly match the subscription product ID you
create in both App Store Connect and Google Play Console (see the root
README's "Go-Live checklist").

## 2. Install and add native platforms

```bash
cd mobile
npm install
npx cap add ios       # macOS + Xcode only
npx cap add android    # needs Android Studio / SDK
npx cap sync
```

`cap sync` copies `www/` into both native projects and wires up
cordova-plugin-purchase's native code.

## 3. Configure app icon, splash screen, and permissions

- Replace the generated icon/splash placeholders with the assets in
  `../store-assets/icon/` (see root README).
- iOS: open `ios/App/App.xcworkspace` in Xcode, set your Team/signing,
  bundle ID (`com.marcustoh.stockscanner`), and add the
  **In-App Purchase** capability under Signing & Capabilities.
- Android: open `android/` in Android Studio, set `applicationId` to
  `com.marcustoh.stockscanner` in `android/app/build.gradle`, and add the
  `com.android.vending.BILLING` permission (cordova-plugin-purchase's
  Android install script normally adds this automatically — verify it's in
  `android/app/src/main/AndroidManifest.xml`).

## 4. The purchase flow needs live verification against a sandbox account

`www/purchases.js` implements the subscribe/restore flow against
cordova-plugin-purchase's stable top-level API (`register`, `order`,
`restorePurchases`, the `approved`/`verified` transaction events). The one
piece marked `TODO` in that file — exactly which field on the native
`transaction` object holds the raw receipt to forward to
`/api/iap/apple/verify` / `/api/iap/google/verify` — was written from the
plugin's documentation, not a live test (this environment has no App Store
Connect or Play Console sandbox account to purchase against). **Before
submitting for review:**

1. Run the app on a real device/simulator with a Sandbox Apple ID / Google
   Play license tester account.
2. Trigger a purchase, `console.log(transaction)` in the `approved` handler,
   and confirm the field paths in `purchases.js` match what's actually
   there.
3. Confirm the backend's `/api/iap/apple/verify` and `/api/iap/google/verify`
   endpoints (see root README) return `active: true` and that the app then
   unlocks the main view.
4. Test **Restore purchases** on a second device/reinstall.

## 5. Build & submit

- **iOS**: Xcode &rarr; Product &rarr; Archive &rarr; Distribute App &rarr; App Store
  Connect. Then finish the listing and submit for review in App Store
  Connect (see root README checklist).
- **Android**: Android Studio &rarr; Build &rarr; Generate Signed Bundle (AAB)
  &rarr; upload to Google Play Console's Internal Testing track first, then
  promote to Production once verified.

## Local web preview (no native shell)

`www/` is plain HTML/JS and can be opened in a browser for UI iteration, but
the purchase flow will no-op (`CdvPurchase` only exists inside the built
native app) — `Purchases.purchaseMonthly()` will just show an error. Use the
`backend/app/static/` web demo (with the login-only flow) for testing the
API without purchases.

```bash
npm run serve   # http://localhost:8100, requires http-server or similar
```
