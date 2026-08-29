from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Subscription, User
from app.schemas import AppleVerifyRequest, GoogleVerifyRequest, SubscriptionStatus
from app.services.apple_iap import AppleNotConfigured, AppleVerificationError, verify_apple_transaction
from app.services.google_iap import GoogleNotConfigured, GoogleVerificationError, verify_google_purchase

router = APIRouter(prefix="/api/iap", tags=["iap"])


def _upsert_subscription(
    db: Session,
    user: User,
    *,
    platform: str,
    product_id: str,
    external_id: str,
    status_value: str,
    expires_at,
    environment: str,
) -> Subscription:
    sub = db.query(Subscription).filter(Subscription.external_id == external_id).first()
    if sub is None:
        sub = Subscription(user_id=user.id, external_id=external_id)
        db.add(sub)
    elif sub.user_id != user.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This purchase is already linked to a different account."
        )

    sub.platform = platform
    sub.product_id = product_id
    sub.status = status_value
    sub.expires_at = expires_at
    sub.environment = environment
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/apple/verify", response_model=SubscriptionStatus)
def verify_apple(
    body: AppleVerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionStatus:
    try:
        info = verify_apple_transaction(body.signed_transaction_info)
    except AppleNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    except AppleVerificationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    if info.revoked:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This transaction was refunded/revoked.")

    sub = _upsert_subscription(
        db,
        user,
        platform="ios",
        product_id=info.product_id,
        external_id=info.original_transaction_id,
        status_value="active",
        expires_at=info.expires_at,
        environment=info.environment.lower(),
    )
    return SubscriptionStatus(
        active=sub.is_active(),
        platform=sub.platform,
        product_id=sub.product_id,
        status=sub.status,
        expires_at=sub.expires_at.isoformat() if sub.expires_at else None,
    )


@router.post("/google/verify", response_model=SubscriptionStatus)
def verify_google(
    body: GoogleVerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionStatus:
    try:
        info = verify_google_purchase(body.product_id, body.purchase_token)
    except GoogleNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    except GoogleVerificationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    if not info.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This subscription is not currently active.")

    sub = _upsert_subscription(
        db,
        user,
        platform="android",
        product_id=info.product_id,
        external_id=info.purchase_token,
        status_value="active",
        expires_at=info.expires_at,
        environment="production",
    )
    return SubscriptionStatus(
        active=sub.is_active(),
        platform=sub.platform,
        product_id=sub.product_id,
        status=sub.status,
        expires_at=sub.expires_at.isoformat() if sub.expires_at else None,
    )
