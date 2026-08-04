import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.subscription_tier import SubscriptionTier
from app.models.tier_role_mapping import TierRoleMapping
from app.schemas.subscription_tier import TierCreate, TierOut


def test_tier_create_rejects_non_positive_price():
    with pytest.raises(ValidationError):
        TierCreate(name="Bronze", price=0, duration_days=30, discord_role_id="123456789012345678")


def test_tier_create_applies_defaults():
    tier = TierCreate(name="Bronze", price=4.99, duration_days=30, discord_role_id="123456789012345678")

    assert tier.currency == "USD"
    assert tier.description is None


def test_tier_out_from_tier_flattens_role_mapping():
    tier = SubscriptionTier(
        id=uuid.uuid4(),
        guild_id=uuid.uuid4(),
        name="Bronze",
        description="Perk one\nPerk two",
        price=4.99,
        currency="USD",
        duration_days=30,
        active=True,
        display_order=0,
        created_at=datetime.now(timezone.utc),
    )
    tier.role_mapping = TierRoleMapping(discord_role_id="123456789012345678")

    out = TierOut.from_tier(tier)

    assert out.discord_role_id == "123456789012345678"
    assert out.price == 4.99
