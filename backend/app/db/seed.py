"""Seed the three MVP subscription tiers for the active guild, and keep their
Discord role mappings in sync with DISCORD_ROLE_ID_TIER_1/2/3. Safe to re-run.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_active_guild
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import SubscriptionTier
from app.schemas.subscription_tier import TierCreate, TierUpdate
from app.services import subscription_tiers as tier_service

settings = get_settings()


def _seed_tiers() -> list[TierCreate]:
    return [
        TierCreate(
            name="Bronze",
            description="Access to the community lounge\nMonthly community Q&A",
            price=4.99,
            duration_days=30,
            discord_role_id=settings.discord_role_id_tier_1 or "000000000000000001",
        ),
        TierCreate(
            name="Silver",
            description="Everything in Bronze\nExclusive Silver-only channels\nPriority support",
            price=9.99,
            duration_days=30,
            discord_role_id=settings.discord_role_id_tier_2 or "000000000000000002",
        ),
        TierCreate(
            name="Gold",
            description="Everything in Silver\nVIP badge and colored name\n1-on-1 support access",
            price=19.99,
            duration_days=30,
            discord_role_id=settings.discord_role_id_tier_3 or "000000000000000003",
        ),
    ]


async def seed_tiers(db: AsyncSession) -> None:
    """Create the three MVP tiers if missing, and sync each one's Discord role
    from DISCORD_ROLE_ID_TIER_1/2/3 if it has since changed in the environment.
    """
    guild = await get_active_guild(db=db)
    seed_data = _seed_tiers()

    existing_result = await db.execute(
        select(SubscriptionTier)
        .options(selectinload(SubscriptionTier.role_mapping))
        .where(SubscriptionTier.guild_id == guild.id)
    )
    existing_by_name = {tier.name: tier for tier in existing_result.scalars().all()}

    created = 0
    synced = 0
    for order, data in enumerate(seed_data):
        tier = existing_by_name.get(data.name)
        if tier is None:
            tier = await tier_service.create_tier(db, guild.id, data)
            tier.display_order = order
            created += 1
        elif tier.role_mapping.discord_role_id != data.discord_role_id:
            await tier_service.update_tier(
                db, guild.id, tier.id, TierUpdate(discord_role_id=data.discord_role_id)
            )
            synced += 1

    await db.commit()
    print(f"Seeded {created} new tier(s), synced {synced} role ID(s) from environment.")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await seed_tiers(db)


if __name__ == "__main__":
    asyncio.run(main())
