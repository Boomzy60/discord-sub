import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import SubscriptionStatus
from app.models.subscription import Subscription
from app.models.subscription_tier import SubscriptionTier


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tier_name: str
    price: float
    currency: str
    status: SubscriptionStatus
    expires_at: datetime

    @classmethod
    def from_subscription(cls, subscription: Subscription, tier: SubscriptionTier) -> "SubscriptionOut":
        return cls(
            id=subscription.id,
            tier_name=tier.name,
            price=float(tier.price),
            currency=tier.currency,
            status=subscription.status,
            expires_at=subscription.expires_at,
        )
