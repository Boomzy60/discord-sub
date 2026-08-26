import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import SubscriptionTier, User
from app.services.payments.stripe_provider import StripeAPIError, StripeProvider
from app.services.subscription_service import start_checkout

router = APIRouter(prefix="/payments/stripe", tags=["payments"])


@router.post("/checkout/{tier_id}")
async def create_stripe_checkout(
    tier_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tier = await db.get(SubscriptionTier, tier_id)
    if tier is None or not tier.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription tier not found")

    provider = StripeProvider()
    try:
        payment, checkout_url = await start_checkout(db, user=user, tier=tier, provider=provider)
    except StripeAPIError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return {
        "success": True,
        "data": {"checkout_url": checkout_url, "payment_id": str(payment.id)},
        "error": None,
    }
