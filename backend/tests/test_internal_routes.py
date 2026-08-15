from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.models import Guild, Subscription, SubscriptionTier, TierRoleMapping, User
from app.models.enums import BillingPeriod, SubscriptionStatus

AUTH_HEADER = "X-Internal-Secret"


async def _seed_active_subscription(db_session, *, guild_id="111", role_id="333", discord_user_id="222"):
    guild = Guild(guild_id=guild_id, guild_name="Test Guild")
    user = User(discord_id=discord_user_id, username="tester")
    db_session.add_all([guild, user])
    await db_session.flush()

    tier = SubscriptionTier(
        guild_id=guild.id,
        name="Gold",
        price=10,
        currency="USD",
        billing_period=BillingPeriod.MONTHLY,
        duration_days=30,
    )
    db_session.add(tier)
    await db_session.flush()

    mapping = TierRoleMapping(guild_id=guild.id, tier_id=tier.id, discord_role_id=role_id)
    subscription = Subscription(
        user_id=user.id,
        tier_id=tier.id,
        status=SubscriptionStatus.ACTIVE,
        starts_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db_session.add_all([mapping, subscription])
    await db_session.commit()

    return guild, tier, user, subscription


async def test_active_roles_rejects_missing_secret(client, db_session):
    await _seed_active_subscription(db_session)

    response = await client.get(
        "/internal/subscriptions/active-roles", params={"discord_user_id": "222", "guild_id": "111"}
    )

    assert response.status_code == 401


async def test_active_roles_rejects_wrong_secret(client, db_session):
    await _seed_active_subscription(db_session)

    response = await client.get(
        "/internal/subscriptions/active-roles",
        params={"discord_user_id": "222", "guild_id": "111"},
        headers={AUTH_HEADER: "wrong-secret"},
    )

    assert response.status_code == 401


async def test_active_roles_returns_role_ids_for_active_subscription(client, db_session):
    await _seed_active_subscription(db_session)
    secret = get_settings().bot_internal_api_secret

    response = await client.get(
        "/internal/subscriptions/active-roles",
        params={"discord_user_id": "222", "guild_id": "111"},
        headers={AUTH_HEADER: secret},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"role_ids": ["333"]}, "error": None}


async def test_active_roles_excludes_expired_subscription(client, db_session):
    _, _, _, subscription = await _seed_active_subscription(db_session)
    subscription.status = SubscriptionStatus.EXPIRED
    await db_session.commit()
    secret = get_settings().bot_internal_api_secret

    response = await client.get(
        "/internal/subscriptions/active-roles",
        params={"discord_user_id": "222", "guild_id": "111"},
        headers={AUTH_HEADER: secret},
    )

    assert response.json()["data"]["role_ids"] == []


async def test_active_roles_scoped_to_guild(client, db_session):
    await _seed_active_subscription(db_session, guild_id="111", role_id="333", discord_user_id="222")
    secret = get_settings().bot_internal_api_secret

    response = await client.get(
        "/internal/subscriptions/active-roles",
        params={"discord_user_id": "222", "guild_id": "999"},
        headers={AUTH_HEADER: secret},
    )

    assert response.json()["data"]["role_ids"] == []


async def test_active_roles_empty_for_unknown_user(client, db_session):
    secret = get_settings().bot_internal_api_secret

    response = await client.get(
        "/internal/subscriptions/active-roles",
        params={"discord_user_id": "does-not-exist", "guild_id": "111"},
        headers={AUTH_HEADER: secret},
    )

    assert response.status_code == 200
    assert response.json()["data"]["role_ids"] == []
