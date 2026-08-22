from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Subscription, SubscriptionTier, User
from app.models.enums import SubscriptionStatus
from app.schemas.subscription import SubscriptionOut

router = APIRouter(tags=["subscriptions"])


@router.get("/subscriptions/me")
async def list_my_subscriptions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Subscription, SubscriptionTier)
        .join(SubscriptionTier, SubscriptionTier.id == Subscription.tier_id)
        .where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.expires_at > now,
        )
        .order_by(SubscriptionTier.display_order)
    )
    data = [
        SubscriptionOut.from_subscription(subscription, tier).model_dump(mode="json")
        for subscription, tier in result.all()
    ]
    return {"success": True, "data": data, "error": None}
