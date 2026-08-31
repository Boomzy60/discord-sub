import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BillingPeriod
from app.models.subscription_tier import SubscriptionTier


class TierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = None
    price: float = Field(gt=0)
    currency: str = "USD"
    billing_period: BillingPeriod = BillingPeriod.MONTHLY
    duration_days: int = Field(gt=0)
    discord_role_id: str = Field(min_length=1)


class TierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    currency: str | None = None
    billing_period: BillingPeriod | None = None
    duration_days: int | None = Field(default=None, gt=0)
    discord_role_id: str | None = Field(default=None, min_length=1)
    active: bool | None = None
    display_order: int | None = None


class TierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    price: float
    currency: str
    billing_period: BillingPeriod
    duration_days: int
    active: bool
    display_order: int
    discord_role_id: str
    created_at: datetime

    @classmethod
    def from_tier(cls, tier: SubscriptionTier) -> "TierOut":
        return cls(
            id=tier.id,
            name=tier.name,
            description=tier.description,
            price=float(tier.price),
            currency=tier.currency,
            billing_period=tier.billing_period,
            duration_days=tier.duration_days,
            active=tier.active,
            display_order=tier.display_order,
            discord_role_id=tier.role_mapping.discord_role_id,
            created_at=tier.created_at,
        )
