import json
from datetime import datetime, timedelta, timezone

import respx
from httpx import Response

from app.core.config import get_settings
from app.jobs.expire_subscriptions import expire_due_subscriptions
from app.models import Guild, Subscription, SubscriptionTier, TierRoleMapping, User
from app.models.enums import BillingPeriod, SubscriptionStatus


async def _seed_active_subscription(
    db_session, *, expires_at, guild_id="111", role_id="333", discord_user_id="222"
):
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
        starts_at=datetime.now(timezone.utc) - timedelta(days=30),
        expires_at=expires_at,
    )
    db_session.add_all([mapping, subscription])
    await db_session.commit()

    return guild, tier, user, subscription


@respx.mock
async def test_expire_due_subscriptions_revokes_role_and_marks_expired(db_session):
    settings = get_settings()
    _, _, _, subscription = await _seed_active_subscription(
        db_session, expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )

    remove_route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/remove").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": False}, "error": None})
    )
    respx.post(f"{settings.bot_internal_api_url}/internal/notify/subscription-expired").mock(
        return_value=Response(200, json={"success": True, "data": {"sent": True}, "error": None})
    )

    expired_count = await expire_due_subscriptions(db_session)

    assert expired_count == 1
    assert remove_route.called
    request_body = json.loads(remove_route.calls.last.request.content)
    assert request_body == {"guild_id": "111", "user_id": "222", "role_id": "333"}

    await db_session.refresh(subscription)
    assert subscription.status == SubscriptionStatus.EXPIRED


@respx.mock
async def test_expire_due_subscriptions_sends_expired_notification_with_tier_details(db_session):
    settings = get_settings()
    _, _, _, subscription = await _seed_active_subscription(
        db_session, expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )

    respx.post(f"{settings.bot_internal_api_url}/internal/roles/remove").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": False}, "error": None})
    )
    notify_route = respx.post(
        f"{settings.bot_internal_api_url}/internal/notify/subscription-expired"
    ).mock(return_value=Response(200, json={"success": True, "data": {"sent": True}, "error": None}))

    await expire_due_subscriptions(db_session)

    assert notify_route.called
    request_body = json.loads(notify_route.calls.last.request.content)
    assert request_body["user_id"] == "222"
    assert request_body["username"] == "tester"
    assert request_body["tier_name"] == "Gold"
    assert request_body["expired_at"] == subscription.expires_at.isoformat()


@respx.mock
async def test_expire_due_subscriptions_ignores_subscriptions_not_yet_expired(db_session):
    settings = get_settings()
    await _seed_active_subscription(
        db_session, expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )

    remove_route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/remove").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": False}, "error": None})
    )

    expired_count = await expire_due_subscriptions(db_session)

    assert expired_count == 0
    assert not remove_route.called


@respx.mock
async def test_expire_due_subscriptions_ignores_already_expired_subscriptions(db_session):
    settings = get_settings()
    _, _, _, subscription = await _seed_active_subscription(
        db_session, expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    subscription.status = SubscriptionStatus.EXPIRED
    await db_session.commit()

    remove_route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/remove").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": False}, "error": None})
    )

    expired_count = await expire_due_subscriptions(db_session)

    assert expired_count == 0
    assert not remove_route.called


@respx.mock
async def test_expire_due_subscriptions_still_expires_when_role_removal_fails(db_session):
    settings = get_settings()
    _, _, _, subscription = await _seed_active_subscription(
        db_session, expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )

    respx.post(f"{settings.bot_internal_api_url}/internal/roles/remove").mock(
        return_value=Response(404, json={"success": False, "data": None, "error": "Member not found"})
    )
    respx.post(f"{settings.bot_internal_api_url}/internal/notify/subscription-expired").mock(
        return_value=Response(200, json={"success": True, "data": {"sent": True}, "error": None})
    )

    expired_count = await expire_due_subscriptions(db_session)

    assert expired_count == 1
    await db_session.refresh(subscription)
    assert subscription.status == SubscriptionStatus.EXPIRED


@respx.mock
async def test_expire_due_subscriptions_processes_multiple_rows_in_one_sweep(db_session):
    settings = get_settings()
    await _seed_active_subscription(
        db_session,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        guild_id="111",
        role_id="333",
    )
    await _seed_active_subscription(
        db_session,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=2),
        guild_id="444",
        role_id="555",
        discord_user_id="666",
    )

    respx.post(f"{settings.bot_internal_api_url}/internal/roles/remove").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": False}, "error": None})
    )
    respx.post(f"{settings.bot_internal_api_url}/internal/notify/subscription-expired").mock(
        return_value=Response(200, json={"success": True, "data": {"sent": True}, "error": None})
    )

    expired_count = await expire_due_subscriptions(db_session)

    assert expired_count == 2
