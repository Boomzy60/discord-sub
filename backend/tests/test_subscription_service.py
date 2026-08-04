import json
from datetime import datetime, timedelta, timezone

import respx
from httpx import Response
from sqlalchemy import select

from app.core.config import get_settings
from app.models import Guild, Payment, Subscription, SubscriptionTier, TierRoleMapping, User
from app.models.enums import BillingPeriod, PaymentProvider, PaymentStatus, SubscriptionStatus
from app.services.payments.base import CreatedPayment, ParsedWebhookEvent, PaymentProvider as PaymentProviderBase
from app.services.subscription_service import (
    SubscriptionActivationError,
    activate_subscription,
    process_webhook,
    start_checkout,
)


class FakeProvider(PaymentProviderBase):
    """In-memory provider for testing the activation flow without any real payment API."""

    name = PaymentProvider.PAYPAL

    def __init__(self, *, verify_result: bool = True, event: ParsedWebhookEvent | None = None):
        self._verify_result = verify_result
        self._event = event

    async def create_payment(self, *, amount, currency, reference, description) -> CreatedPayment:
        return CreatedPayment(
            provider_transaction_id=f"fake-txn-{reference}",
            checkout_url="https://fake-provider.test/checkout",
            raw_payload={"amount": amount, "currency": currency, "reference": reference},
        )

    async def verify_webhook(self, headers, body) -> bool:
        return self._verify_result

    def parse_webhook_event(self, headers, body) -> ParsedWebhookEvent:
        return self._event


async def _seed_guild_tier_user(db_session, *, duration_days: int = 30):
    guild = Guild(guild_id="111", guild_name="Test Guild")
    user = User(discord_id="222", username="tester")
    db_session.add_all([guild, user])
    await db_session.flush()

    tier = SubscriptionTier(
        guild_id=guild.id,
        name="Gold",
        price=10,
        currency="USD",
        billing_period=BillingPeriod.MONTHLY,
        duration_days=duration_days,
    )
    db_session.add(tier)
    await db_session.flush()

    mapping = TierRoleMapping(guild_id=guild.id, tier_id=tier.id, discord_role_id="333")
    db_session.add(mapping)
    await db_session.commit()

    return guild, tier, user


async def test_start_checkout_creates_pending_subscription_and_payment(db_session):
    _, tier, user = await _seed_guild_tier_user(db_session)
    provider = FakeProvider()

    payment, checkout_url = await start_checkout(db_session, user=user, tier=tier, provider=provider)

    assert checkout_url == "https://fake-provider.test/checkout"
    assert payment.status == PaymentStatus.PENDING
    assert payment.provider == PaymentProvider.PAYPAL

    subscription = await db_session.get(Subscription, payment.subscription_id)
    assert subscription.status == SubscriptionStatus.PENDING


@respx.mock
async def test_activate_subscription_marks_paid_and_assigns_role(db_session):
    settings = get_settings()
    guild, tier, user = await _seed_guild_tier_user(db_session)
    provider = FakeProvider()
    payment, _ = await start_checkout(db_session, user=user, tier=tier, provider=provider)

    route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": True}, "error": None})
    )

    subscription = await activate_subscription(db_session, payment)
    await db_session.commit()

    assert route.called
    request_body = json.loads(route.calls.last.request.content)
    assert request_body == {"guild_id": "111", "user_id": "222", "role_id": "333"}

    assert payment.status == PaymentStatus.PAID
    assert payment.paid_at is not None
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.expires_at > datetime.now(timezone.utc)


async def test_activate_subscription_raises_without_linked_subscription(db_session):
    payment = Payment(
        user_id="00000000-0000-0000-0000-000000000000",
        subscription_id=None,
        provider=PaymentProvider.PAYPAL,
        payment_method="paypal",
        amount=10,
        currency="USD",
        provider_transaction_id="orphan-txn",
        status=PaymentStatus.PENDING,
    )

    try:
        await activate_subscription(db_session, payment)
        assert False, "expected SubscriptionActivationError"
    except SubscriptionActivationError:
        pass


@respx.mock
async def test_process_webhook_full_flow_activates_and_assigns_role(db_session):
    settings = get_settings()
    guild, tier, user = await _seed_guild_tier_user(db_session)

    checkout_provider = FakeProvider()
    payment, _ = await start_checkout(db_session, user=user, tier=tier, provider=checkout_provider)

    event = ParsedWebhookEvent(
        provider_event_id="evt-1",
        event_type="PAYMENT.CAPTURE.COMPLETED",
        provider_transaction_id=payment.provider_transaction_id,
        status=PaymentStatus.PAID,
        raw_payload={"id": "evt-1"},
    )
    webhook_provider = FakeProvider(verify_result=True, event=event)

    route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": True}, "error": None})
    )

    webhook_row = await process_webhook(db_session, webhook_provider, {}, b"{}")

    assert route.called
    assert webhook_row.processed is True

    refreshed_payment = await db_session.get(Payment, payment.id)
    assert refreshed_payment.status == PaymentStatus.PAID


@respx.mock
async def test_process_webhook_is_idempotent_for_repeated_events(db_session):
    settings = get_settings()
    guild, tier, user = await _seed_guild_tier_user(db_session)

    checkout_provider = FakeProvider()
    payment, _ = await start_checkout(db_session, user=user, tier=tier, provider=checkout_provider)

    event = ParsedWebhookEvent(
        provider_event_id="evt-dup",
        event_type="PAYMENT.CAPTURE.COMPLETED",
        provider_transaction_id=payment.provider_transaction_id,
        status=PaymentStatus.PAID,
        raw_payload={"id": "evt-dup"},
    )
    webhook_provider = FakeProvider(verify_result=True, event=event)

    route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": True}, "error": None})
    )

    await process_webhook(db_session, webhook_provider, {}, b"{}")
    await process_webhook(db_session, webhook_provider, {}, b"{}")

    assert route.call_count == 1


async def test_process_webhook_raises_on_invalid_signature(db_session):
    from app.services.payments.base import WebhookVerificationError

    provider = FakeProvider(verify_result=False)

    try:
        await process_webhook(db_session, provider, {}, b"{}")
        assert False, "expected WebhookVerificationError"
    except WebhookVerificationError:
        pass


@respx.mock
async def test_activate_subscription_rejects_terminal_payment_status(db_session):
    settings = get_settings()
    _, tier, user = await _seed_guild_tier_user(db_session)
    provider = FakeProvider()
    payment, _ = await start_checkout(db_session, user=user, tier=tier, provider=provider)
    payment.status = PaymentStatus.FAILED
    await db_session.commit()

    route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": True}, "error": None})
    )

    try:
        await activate_subscription(db_session, payment)
        assert False, "expected SubscriptionActivationError"
    except SubscriptionActivationError:
        pass

    assert not route.called


@respx.mock
async def test_activate_subscription_raises_when_tier_has_no_role_mapping(db_session):
    settings = get_settings()
    guild = Guild(guild_id="444", guild_name="Unmapped Guild")
    user = User(discord_id="555", username="tester2")
    db_session.add_all([guild, user])
    await db_session.flush()

    tier = SubscriptionTier(
        guild_id=guild.id,
        name="Unmapped",
        price=5,
        currency="USD",
        billing_period=BillingPeriod.MONTHLY,
        duration_days=30,
    )
    db_session.add(tier)
    await db_session.commit()

    provider = FakeProvider()
    payment, _ = await start_checkout(db_session, user=user, tier=tier, provider=provider)

    route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": True}, "error": None})
    )

    try:
        await activate_subscription(db_session, payment)
        assert False, "expected SubscriptionActivationError"
    except SubscriptionActivationError:
        pass

    assert not route.called
    refreshed_payment = await db_session.get(Payment, payment.id)
    assert refreshed_payment.status == PaymentStatus.PENDING


@respx.mock
async def test_activate_subscription_renewal_extends_from_current_expiry(db_session):
    settings = get_settings()
    _, tier, user = await _seed_guild_tier_user(db_session)
    provider = FakeProvider()
    first_payment, _ = await start_checkout(db_session, user=user, tier=tier, provider=provider)

    respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": True}, "error": None})
    )

    first_subscription = await activate_subscription(db_session, first_payment)
    await db_session.commit()
    first_expiry = first_subscription.expires_at

    renewal_payment = Payment(
        user_id=user.id,
        subscription_id=first_subscription.id,
        provider=PaymentProvider.PAYPAL,
        payment_method="paypal",
        amount=tier.price,
        currency=tier.currency,
        provider_transaction_id="fake-txn-renewal",
        status=PaymentStatus.PENDING,
    )
    db_session.add(renewal_payment)
    await db_session.commit()

    renewed_subscription = await activate_subscription(db_session, renewal_payment)
    await db_session.commit()

    assert renewed_subscription.id == first_subscription.id
    expected_expiry = first_expiry + timedelta(days=tier.duration_days)
    assert abs((renewed_subscription.expires_at - expected_expiry).total_seconds()) < 1
