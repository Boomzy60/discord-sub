import pytest
from fastapi import HTTPException

from app.models import Guild
from app.schemas.subscription_tier import TierCreate, TierUpdate
from app.services import subscription_tiers as tier_service


async def _make_guild(db_session) -> Guild:
    guild = Guild(guild_id="test-guild", guild_name="Test Guild", active=True)
    db_session.add(guild)
    await db_session.commit()
    await db_session.refresh(guild)
    return guild


async def test_create_tier_creates_tier_and_role_mapping(db_session):
    guild = await _make_guild(db_session)

    tier = await tier_service.create_tier(
        db_session, guild.id, TierCreate(name="Bronze", price=4.99, duration_days=30, discord_role_id="111")
    )

    assert tier.name == "Bronze"
    assert tier.role_mapping.discord_role_id == "111"
    assert tier.billing_period.value == "MONTHLY"


async def test_list_tiers_orders_by_display_order_and_filters_active(db_session):
    guild = await _make_guild(db_session)
    tier_a = await tier_service.create_tier(
        db_session, guild.id, TierCreate(name="A", price=1, duration_days=30, discord_role_id="1")
    )
    tier_b = await tier_service.create_tier(
        db_session, guild.id, TierCreate(name="B", price=2, duration_days=30, discord_role_id="2")
    )
    tier_a.display_order = 1
    tier_b.display_order = 0
    await db_session.commit()
    await tier_service.deactivate_tier(db_session, guild.id, tier_a.id)

    active_only = await tier_service.list_tiers(db_session, guild.id, only_active=True)
    all_tiers = await tier_service.list_tiers(db_session, guild.id, only_active=False)

    assert [t.name for t in active_only] == ["B"]
    assert [t.name for t in all_tiers] == ["B", "A"]


async def test_update_tier_updates_fields_and_role_mapping(db_session):
    guild = await _make_guild(db_session)
    tier = await tier_service.create_tier(
        db_session, guild.id, TierCreate(name="Bronze", price=4.99, duration_days=30, discord_role_id="111")
    )

    updated = await tier_service.update_tier(
        db_session, guild.id, tier.id, TierUpdate(price=9.99, discord_role_id="222")
    )

    assert float(updated.price) == 9.99
    assert updated.role_mapping.discord_role_id == "222"
    assert updated.name == "Bronze"


async def test_update_tier_raises_404_for_unknown_tier(db_session):
    guild = await _make_guild(db_session)

    with pytest.raises(HTTPException) as exc_info:
        await tier_service.update_tier(db_session, guild.id, guild.id, TierUpdate(price=1))

    assert exc_info.value.status_code == 404


async def test_deactivate_tier_sets_active_false(db_session):
    guild = await _make_guild(db_session)
    tier = await tier_service.create_tier(
        db_session, guild.id, TierCreate(name="Bronze", price=4.99, duration_days=30, discord_role_id="111")
    )

    await tier_service.deactivate_tier(db_session, guild.id, tier.id)
    await db_session.refresh(tier)

    assert tier.active is False
