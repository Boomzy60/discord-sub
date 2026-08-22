import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import SubscriptionTier, User
from app.services.payments.nowpayments import NOWPaymentsAPIError, NOWPaymentsProvider
from app.services.subscription_service import start_checkout

router = APIRouter(prefix="/payments/crypto", tags=["payments"])


class CryptoCheckoutRequest(BaseModel):
    pay_currency: str | None = None


async def _get_active_tier(tier_id: uuid.UUID, db: AsyncSession) -> SubscriptionTier:
    tier = await db.get(SubscriptionTier, tier_id)
    if tier is None or not tier.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription tier not found")
    return tier


@router.get("/currencies/{tier_id}")
async def list_crypto_currencies(
    tier_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tier = await _get_active_tier(tier_id, db)

    provider = NOWPaymentsProvider()
    currencies = await provider.get_available_currencies(
        amount=float(tier.price), currency=tier.currency
    )

    return {"success": True, "data": currencies, "error": None}


@router.post("/checkout/{tier_id}")
async def create_crypto_checkout(
    tier_id: uuid.UUID,
    body: CryptoCheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tier = await _get_active_tier(tier_id, db)

    if not body.pay_currency:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "pay_currency is required")
    pay_currency = body.pay_currency.lower()

    provider = NOWPaymentsProvider()
    available = await provider.get_available_currencies(
        amount=float(tier.price), currency=tier.currency
    )
    if pay_currency not in {entry["code"] for entry in available}:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{pay_currency.upper()} is not available for this plan's price; "
            "please pick another currency.",
        )

    try:
        payment, checkout_url = await start_checkout(
            db, user=user, tier=tier, provider=provider, pay_currency=pay_currency
        )
    except NOWPaymentsAPIError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return {
        "success": True,
        "data": {"checkout_url": checkout_url, "payment_id": str(payment.id)},
        "error": None,
    }
