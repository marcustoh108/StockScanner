"""Apple App Store server-side receipt verification.

Verifies a StoreKit 2 `signedTransactionInfo` JWS (sent by the iOS app right
after a purchase or restore) using Apple's official app-store-server-library.
This needs credentials only obtainable from an active App Store Connect
account -- see README "Go-Live checklist" for how to generate them. Until
those env vars are set, `verify_apple_transaction` raises AppleNotConfigured
so the rest of the API keeps working in development.
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from functools import lru_cache


class AppleNotConfigured(Exception):
    pass


class AppleVerificationError(Exception):
    pass


@dataclass
class AppleSubscriptionInfo:
    product_id: str
    original_transaction_id: str
    expires_at: dt.datetime | None
    environment: str  # "Sandbox" | "Production"
    revoked: bool


def _env(name: str) -> str | None:
    return os.environ.get(name) or None


@lru_cache(maxsize=1)
def _get_verifier():
    try:
        from appstoreserverlibrary.models.Environment import Environment
        from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise AppleNotConfigured(
            "app-store-server-library is not installed."
        ) from exc

    bundle_id = _env("APPLE_BUNDLE_ID")
    root_cert_dir = _env("APPLE_ROOT_CERT_DIR")
    environment_name = _env("APPLE_ENVIRONMENT") or "Sandbox"
    app_apple_id = _env("APPLE_APP_APPLE_ID")

    if not bundle_id or not root_cert_dir:
        raise AppleNotConfigured(
            "APPLE_BUNDLE_ID and APPLE_ROOT_CERT_DIR must be set to verify Apple purchases. "
            "See README: Go-Live checklist > Apple."
        )

    cert_dir_path = root_cert_dir
    if not os.path.isdir(cert_dir_path):
        raise AppleNotConfigured(f"APPLE_ROOT_CERT_DIR '{cert_dir_path}' does not exist.")

    root_certificates = []
    for fname in sorted(os.listdir(cert_dir_path)):
        if fname.lower().endswith((".cer", ".der")):
            with open(os.path.join(cert_dir_path, fname), "rb") as f:
                root_certificates.append(f.read())
    if not root_certificates:
        raise AppleNotConfigured(f"No .cer/.der root certificates found in '{cert_dir_path}'.")

    environment = Environment.PRODUCTION if environment_name == "Production" else Environment.SANDBOX

    return SignedDataVerifier(
        root_certificates=root_certificates,
        enable_online_checks=True,
        bundle_id=bundle_id,
        app_apple_id=int(app_apple_id) if app_apple_id else None,
        environment=environment,
    )


def verify_apple_transaction(signed_transaction_info: str) -> AppleSubscriptionInfo:
    verifier = _get_verifier()
    try:
        payload = verifier.verify_and_decode_signed_transaction(signed_transaction_info)
    except AppleNotConfigured:
        raise
    except Exception as exc:
        raise AppleVerificationError(f"Apple signature verification failed: {exc}") from exc

    expires_ms = getattr(payload, "expiresDate", None)
    expires_at = (
        dt.datetime.fromtimestamp(expires_ms / 1000, tz=dt.timezone.utc) if expires_ms else None
    )

    return AppleSubscriptionInfo(
        product_id=payload.productId,
        original_transaction_id=payload.originalTransactionId,
        expires_at=expires_at,
        environment=str(getattr(payload, "environment", "Sandbox")),
        revoked=getattr(payload, "revocationDate", None) is not None,
    )
