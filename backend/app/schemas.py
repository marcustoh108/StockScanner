from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SubscriptionStatus(BaseModel):
    active: bool
    platform: str | None = None
    product_id: str | None = None
    status: str | None = None
    expires_at: str | None = None


class MeResponse(BaseModel):
    email: str
    subscription: SubscriptionStatus


class AppleVerifyRequest(BaseModel):
    signed_transaction_info: str = Field(
        description="The signedTransactionInfo JWS string from StoreKit 2's Transaction.updates / purchase result."
    )


class GoogleVerifyRequest(BaseModel):
    product_id: str
    purchase_token: str
