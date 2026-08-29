"""Google Play server-side subscription verification via the Android
Publisher API. Needs a Google Cloud service account linked to Play Console
-- see README "Go-Live checklist" for how to generate it. Until
GOOGLE_APPLICATION_CREDENTIALS / GOOGLE_PLAY_PACKAGE_NAME are set,
verify_google_purchase raises GoogleNotConfigured so the rest of the API
keeps working in development.
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from functools import lru_cache


class GoogleNotConfigured(Exception):
    pass


class GoogleVerificationError(Exception):
    pass


@dataclass
class GoogleSubscriptionInfo:
    product_id: str
    purchase_token: str
    expires_at: dt.datetime | None
    active: bool


def _env(name: str) -> str | None:
    return os.environ.get(name) or None


@lru_cache(maxsize=1)
def _get_client():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise GoogleNotConfigured("google-api-python-client is not installed.") from exc

    creds_path = _env("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.isfile(creds_path):
        raise GoogleNotConfigured(
            "GOOGLE_APPLICATION_CREDENTIALS must point at a valid service-account JSON key. "
            "See README: Go-Live checklist > Google Play."
        )

    credentials = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/androidpublisher"]
    )
    return build("androidpublisher", "v3", credentials=credentials, cache_discovery=False)


def verify_google_purchase(product_id: str, purchase_token: str) -> GoogleSubscriptionInfo:
    package_name = _env("GOOGLE_PLAY_PACKAGE_NAME")
    if not package_name:
        raise GoogleNotConfigured("GOOGLE_PLAY_PACKAGE_NAME must be set to verify Google purchases.")

    client = _get_client()
    try:
        result = (
            client.purchases()
            .subscriptionsv2()
            .get(packageName=package_name, token=purchase_token)
            .execute()
        )
    except GoogleNotConfigured:
        raise
    except Exception as exc:
        raise GoogleVerificationError(f"Google Play verification failed: {exc}") from exc

    line_items = result.get("lineItems", [])
    expires_at = None
    if line_items:
        expiry_str = line_items[0].get("expiryTime")
        if expiry_str:
            expires_at = dt.datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))

    state = result.get("subscriptionState", "")
    active = state in ("SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD")

    return GoogleSubscriptionInfo(
        product_id=product_id,
        purchase_token=purchase_token,
        expires_at=expires_at,
        active=active,
    )
