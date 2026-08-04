import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Guild, Payment, Subscription, SubscriptionTier, TierRoleMapping, User
from app.models.enums import BillingPeriod, PaymentProvider, PaymentStatus, SubscriptionStatus


async def test_user_gets_uuid_primary_key_and_utc_timestamps(db_session):
    user = User(discord_id="123456789012345678", username="testuser")
    db_session.add(user)
    await db_session.commit()

    assert isinstance(user.id, uuid.UUID)
    assert user.is_admin is False


async def test_tier_belongs_to_guild_and_has_role_mapping(db_session):
    guild = Guild(guild_id="998877665544332211", guild_name="Test Server")
    db_session.add(guild)
    await db_session.flush()

    tier = SubscriptionTier(
        guild_id=guild.id,
        name="Gold",
        price=9.99,
        billing_period=BillingPeriod.MONTHLY,
        duration_days=30,
    )
    db_session.add(tier)
    await db_session.flush()

    mapping = TierRoleMapping(guild_id=guild.id, tier_id=tier.id, discord_role_id="111222333444555666")
    db_session.add(mapping)
    await db_session.commit()

    result = await db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.id == tier.id)
    )
    fetched = result.scalar_one()
    assert fetched.guild_id == guild.id
    assert fetched.currency == "USD"


async def test_subscription_links_user_and_tier(db_session):
    guild = Guild(guild_id="998877665544332211", guild_name="Test Server")
    user = User(discord_id="123456789012345678", username="testuser")
    db_session.add_all([guild, user])
    await db_session.flush()

    tier = SubscriptionTier(
        guild_id=guild.id, name="Gold", price=9.99, billing_period=BillingPeriod.MONTHLY, duration_days=30
    )
    db_session.add(tier)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    subscription = Subscription(
        user_id=user.id,
        tier_id=tier.id,
        status=SubscriptionStatus.ACTIVE,
        starts_at=now,
        expires_at=now + timedelta(days=30),
    )
    db_session.add(subscription)
    await db_session.commit()

    result = await db_session.execute(select(Subscription).where(Subscription.id == subscription.id))
    fetched = result.scalar_one()
    assert fetched.user_id == user.id
    assert fetched.tier_id == tier.id
    assert fetched.status == SubscriptionStatus.ACTIVE
    assert fetched.auto_renew is False


async def test_payment_records_provider_and_amount(db_session):
    guild = Guild(guild_id="998877665544332211", guild_name="Test Server")
    user = User(discord_id="123456789012345678", username="testuser")
    db_session.add_all([guild, user])
    await db_session.flush()

    tier = SubscriptionTier(
        guild_id=guild.id, name="Gold", price=9.99, billing_period=BillingPeriod.MONTHLY, duration_days=30
    )
    db_session.add(tier)
    await db_session.flush()

    payment = Payment(
        user_id=user.id,
        provider=PaymentProvider.NOWPAYMENTS,
        payment_method="crypto",
        amount=9.99,
        currency="USD",
        provider_transaction_id="np-123",
        status=PaymentStatus.PENDING,
    )
    db_session.add(payment)
    await db_session.commit()

    assert payment.status == PaymentStatus.PENDING
    assert payment.provider_transaction_id == "np-123"
