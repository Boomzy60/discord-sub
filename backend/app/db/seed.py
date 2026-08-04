"""Seed the three MVP subscription tiers for the active guild. Safe to re-run."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_guild
from app.db.session import AsyncSessionLocal
from app.models import SubscriptionTier
from app.schemas.subscription_tier import TierCreate
from app.services import subscription_tiers as tier_service

SEED_TIERS: list[TierCreate] = [
    TierCreate(
        name="Bronze",
        description="Access to the community lounge\nMonthly community Q&A",
        price=4.99,
        duration_days=30,
        discord_role_id="000000000000000001",
    ),
    TierCreate(
        name="Silver",
        description="Everything in Bronze\nExclusive Silver-only channels\nPriority support",
        price=9.99,
        duration_days=30,
        discord_role_id="000000000000000002",
    ),
    TierCreate(
        name="Gold",
        description="Everything in Silver\nVIP badge and colored name\n1-on-1 support access",
        price=19.99,
        duration_days=30,
        discord_role_id="000000000000000003",
    ),
]


async def seed_tiers(db: AsyncSession) -> None:
    guild = await get_active_guild(db=db)

    existing = await db.execute(select(SubscriptionTier).where(SubscriptionTier.guild_id == guild.id))
    if existing.scalars().first() is not None:
        print("Tiers already seeded, skipping.")
        return

    for order, data in enumerate(SEED_TIERS):
        tier = await tier_service.create_tier(db, guild.id, data)
        tier.display_order = order

    await db.commit()
    print(f"Seeded {len(SEED_TIERS)} tiers.")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await seed_tiers(db)


if __name__ == "__main__":
    asyncio.run(main())
