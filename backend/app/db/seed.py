"""Seed the six subscription tiers (three tiers x monthly/3-month) for the
active guild, and keep their price, description, and Discord role mapping in
sync with this file / the DISCORD_ROLE_ID_TIER_1/2/3 env vars. Safe to re-run.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_active_guild
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import SubscriptionTier
from app.models.enums import BillingPeriod
from app.schemas.subscription_tier import TierCreate, TierUpdate
from app.services import subscription_tiers as tier_service

settings = get_settings()


def _seed_tiers() -> list[TierCreate]:
    return [
        TierCreate(
            name="Bronze",
            description="1 Shiny regular pokemon/Month",
            price=5.00,
            billing_period=BillingPeriod.MONTHLY,
            duration_days=30,
            discord_role_id=settings.discord_role_id_tier_1 or "000000000000000001",
        ),
        TierCreate(
            name="Bronze (3 Month)",
            description="1 Shiny regular pokemon/Month",
            price=12.00,
            billing_period=BillingPeriod.QUARTERLY,
            duration_days=90,
            discord_role_id=settings.discord_role_id_tier_1 or "000000000000000001",
        ),
        TierCreate(
            name="Silver",
            description="1 Shiny Legendary or Mythical pokemon/Month",
            price=10.00,
            billing_period=BillingPeriod.MONTHLY,
            duration_days=30,
            discord_role_id=settings.discord_role_id_tier_2 or "000000000000000002",
        ),
        TierCreate(
            name="Silver (3 Month)",
            description="1 Shiny Legendary or Mythical pokemon/Month",
            price=24.00,
            billing_period=BillingPeriod.QUARTERLY,
            duration_days=90,
            discord_role_id=settings.discord_role_id_tier_2 or "000000000000000002",
        ),
        TierCreate(
            name="Gold",
            description="2 Shiny Legendary or Mythical pokemon and 1 Shiny regular pokemon/Month",
            price=20.00,
            billing_period=BillingPeriod.MONTHLY,
            duration_days=30,
            discord_role_id=settings.discord_role_id_tier_3 or "000000000000000003",
        ),
        TierCreate(
            name="Gold (3 Month)",
            description="2 Shiny Legendary or Mythical pokemon and 1 Shiny regular pokemon/Month",
            price=48.00,
            billing_period=BillingPeriod.QUARTERLY,
            duration_days=90,
            discord_role_id=settings.discord_role_id_tier_3 or "000000000000000003",
        ),
    ]


async def seed_tiers(db: AsyncSession) -> None:
    """Create the six tiers if missing, and sync each existing tier's price,
    description, display order, and Discord role if they've since changed here.
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
            continue

        changes = {}
        if tier.role_mapping.discord_role_id != data.discord_role_id:
            changes["discord_role_id"] = data.discord_role_id
        if tier.price != data.price:
            changes["price"] = data.price
        if tier.description != data.description:
            changes["description"] = data.description
        if tier.display_order != order:
            changes["display_order"] = order
        if changes:
            await tier_service.update_tier(db, guild.id, tier.id, TierUpdate(**changes))
            synced += 1

    await db.commit()
    print(f"Seeded {created} new tier(s), synced {synced} tier(s) from environment.")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await seed_tiers(db)


if __name__ == "__main__":
    asyncio.run(main())
