from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Subscription, User


def get_active_subscription(user: User, db: Session) -> Subscription | None:
    subs = db.scalars(
        select(Subscription).where(Subscription.user_id == user.id)
    ).all()
    active = [s for s in subs if s.is_active()]
    if not active:
        return None
    active.sort(key=lambda s: s.expires_at or s.updated_at, reverse=True)
    return active[0]


def require_active_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    sub = get_active_subscription(user, db)
    if sub is None:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "An active subscription is required to use this feature.",
        )
    return user
