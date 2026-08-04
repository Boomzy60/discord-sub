from sqlalchemy import select

from app.db.seed import seed_tiers
from app.models import SubscriptionTier


async def test_seed_tiers_creates_three_active_tiers(db_session):
    await seed_tiers(db_session)

    result = await db_session.execute(select(SubscriptionTier))
    tiers = result.scalars().all()

    assert len(tiers) == 3
    assert all(tier.active for tier in tiers)


async def test_seed_tiers_is_idempotent(db_session):
    await seed_tiers(db_session)
    await seed_tiers(db_session)

    result = await db_session.execute(select(SubscriptionTier))
    tiers = result.scalars().all()

    assert len(tiers) == 3
