"""Business logic for managing subscription tiers and their Discord role mappings."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import BillingPeriod
from app.models.subscription_tier import SubscriptionTier
from app.models.tier_role_mapping import TierRoleMapping
from app.schemas.subscription_tier import TierCreate, TierUpdate


async def _get_owned_tier(db: AsyncSession, guild_id: uuid.UUID, tier_id: uuid.UUID) -> SubscriptionTier:
    result = await db.execute(
        select(SubscriptionTier)
        .options(selectinload(SubscriptionTier.role_mapping))
        .where(SubscriptionTier.id == tier_id, SubscriptionTier.guild_id == guild_id)
    )
    tier = result.scalar_one_or_none()
    if tier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tier not found")
    return tier


async def list_tiers(db: AsyncSession, guild_id: uuid.UUID, *, only_active: bool) -> list[SubscriptionTier]:
    """List a guild's tiers ordered for display, optionally excluding inactive ones."""
    stmt = (
        select(SubscriptionTier)
        .options(selectinload(SubscriptionTier.role_mapping))
        .where(SubscriptionTier.guild_id == guild_id)
        .order_by(SubscriptionTier.display_order)
    )
    if only_active:
        stmt = stmt.where(SubscriptionTier.active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_tier(db: AsyncSession, guild_id: uuid.UUID, data: TierCreate) -> SubscriptionTier:
    """Create a tier and its Discord role mapping. MVP is monthly-only, so billing period is fixed."""
    tier = SubscriptionTier(
        guild_id=guild_id,
        name=data.name,
        description=data.description,
        price=data.price,
        currency=data.currency,
        billing_period=BillingPeriod.MONTHLY,
        duration_days=data.duration_days,
    )
    db.add(tier)
    await db.flush()

    db.add(TierRoleMapping(guild_id=guild_id, tier_id=tier.id, discord_role_id=data.discord_role_id))
    await db.commit()

    return await _get_owned_tier(db, guild_id, tier.id)


async def update_tier(
    db: AsyncSession, guild_id: uuid.UUID, tier_id: uuid.UUID, data: TierUpdate
) -> SubscriptionTier:
    tier = await _get_owned_tier(db, guild_id, tier_id)

    update_data = data.model_dump(exclude_unset=True, exclude={"discord_role_id"})
    for field, value in update_data.items():
        setattr(tier, field, value)

    if data.discord_role_id is not None:
        tier.role_mapping.discord_role_id = data.discord_role_id

    await db.commit()
    return await _get_owned_tier(db, guild_id, tier_id)


async def deactivate_tier(db: AsyncSession, guild_id: uuid.UUID, tier_id: uuid.UUID) -> None:
    tier = await _get_owned_tier(db, guild_id, tier_id)
    tier.active = False
    await db.commit()
