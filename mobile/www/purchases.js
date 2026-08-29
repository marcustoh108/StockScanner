// In-app purchase integration using cordova-plugin-purchase (CdvPurchase),
// which works inside Capacitor via `npx cap sync`. It gives one JS API for
// both StoreKit (iOS) and Google Play Billing (Android).
//
// IMPORTANT -- verify before shipping: the exact field names used below to
// pull the verification payload off a `transaction` object (iOS's signed
// JWS, Android's purchaseToken) can change between plugin versions and were
// written from documentation, not tested against a live purchase (this
// sandbox has no iOS/Android runtime or App Store/Play sandbox account to
// test against). Before submitting to the stores: run a real sandbox
// purchase, log the `transaction` object, and confirm these field paths
// match. Plugin docs: https://purchase.cordova.fovea.cc/

const Purchases = (() => {
  const PRODUCT_ID = window.STOCKSCANNER_CONFIG.MONTHLY_PRODUCT_ID;
  let onEntitled = () => {};
  let onError = () => {};

  function store() {
    if (!window.CdvPurchase) return null;
    return window.CdvPurchase.store;
  }

  function init(callbacks) {
    onEntitled = callbacks.onEntitled || onEntitled;
    onError = callbacks.onError || onError;

    const s = store();
    if (!s) {
      // Running in a plain browser (no native shell / plugin not synced yet).
      console.warn("CdvPurchase not available -- run inside the built native app.");
      return;
    }

    const { ProductType, Platform } = window.CdvPurchase;

    s.register([
      { id: PRODUCT_ID, type: ProductType.PAID_SUBSCRIPTION, platform: Platform.APPLE_APPSTORE },
      { id: PRODUCT_ID, type: ProductType.PAID_SUBSCRIPTION, platform: Platform.GOOGLE_PLAY },
    ]);

    s.when(PRODUCT_ID)
      .approved((transaction) => verifyAndFinish(transaction))
      .verified((receipt) => receipt.finish());

    s.error((err) => {
      console.error("Purchase error", err);
      onError(err.message || "Purchase failed.");
    });

    document.addEventListener(
      "deviceready",
      () => s.initialize([Platform.APPLE_APPSTORE, Platform.GOOGLE_PLAY]),
      { once: true }
    );
    // In case deviceready already fired before this script ran.
    if (window.cordova && window.cordova.platformId) {
      s.initialize([Platform.APPLE_APPSTORE, Platform.GOOGLE_PLAY]);
    }
  }

  async function verifyAndFinish(transaction) {
    try {
      const platform = transaction.platform; // "ios-appstore" | "android-playstore" (see plugin docs)
      if (String(platform).includes("ios")) {
        // TODO verify field name against a real StoreKit2 transaction object.
        const jws = transaction.nativePurchase?.jsonRepresentation || transaction.transactionId;
        await Api.verifyApple(jws);
      } else {
        // TODO verify field name against a real Google Play purchase object.
        const token = transaction.nativePurchase?.purchaseToken || transaction.purchaseId;
        await Api.verifyGoogle(PRODUCT_ID, token);
      }
      transaction.finish();
      onEntitled();
    } catch (err) {
      onError(err.message || "Could not verify your purchase with the server.");
    }
  }

  function purchaseMonthly() {
    const s = store();
    if (!s) {
      onError("In-app purchases are only available in the installed app.");
      return;
    }
    const offer = s.get(PRODUCT_ID)?.getOffer();
    if (!offer) {
      onError("Subscription product not loaded yet -- try again in a moment.");
      return;
    }
    s.order(offer);
  }

  function restore() {
    const s = store();
    if (!s) {
      onError("In-app purchases are only available in the installed app.");
      return;
    }
    s.restorePurchases();
  }

  return { init, purchaseMonthly, restore };
})();
