from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token
from app.models import Guild, Subscription, SubscriptionTier, TierRoleMapping, User
from app.models.enums import BillingPeriod, SubscriptionStatus


async def _make_tier(db_session, guild: Guild, *, name: str, price: float, display_order: int) -> SubscriptionTier:
    tier = SubscriptionTier(
        guild_id=guild.id,
        name=name,
        price=price,
        currency="USD",
        billing_period=BillingPeriod.MONTHLY,
        duration_days=30,
        display_order=display_order,
    )
    db_session.add(tier)
    await db_session.flush()
    db_session.add(TierRoleMapping(guild_id=guild.id, tier_id=tier.id, discord_role_id=f"role-{name}"))
    await db_session.commit()
    await db_session.refresh(tier)
    return tier


async def test_list_my_subscriptions_returns_only_active_unexpired(client, db_session):
    user = User(discord_id="1", username="member")
    db_session.add(user)
    guild = Guild(guild_id="guild-1", guild_name="Test Guild", active=True)
    db_session.add(guild)
    await db_session.flush()

    active_tier = await _make_tier(db_session, guild, name="Gold", price=19.99, display_order=1)
    expired_tier = await _make_tier(db_session, guild, name="Bronze", price=4.99, display_order=0)

    now = datetime.now(timezone.utc)
    db_session.add(
        Subscription(
            user_id=user.id,
            tier_id=active_tier.id,
            status=SubscriptionStatus.ACTIVE,
            starts_at=now,
            expires_at=now + timedelta(days=10),
        )
    )
    db_session.add(
        Subscription(
            user_id=user.id,
            tier_id=expired_tier.id,
            status=SubscriptionStatus.EXPIRED,
            starts_at=now - timedelta(days=40),
            expires_at=now - timedelta(days=10),
        )
    )
    await db_session.commit()

    client.cookies.set("session", create_access_token(user.id))

    response = await client.get("/subscriptions/me")

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["tier_name"] == "Gold"
    assert data[0]["status"] == "ACTIVE"


async def test_list_my_subscriptions_requires_auth(client):
    response = await client.get("/subscriptions/me")

    assert response.status_code == 401
