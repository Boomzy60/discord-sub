"""Provider-agnostic subscription activation and checkout orchestration.

This is the only place that turns a confirmed payment into an active
subscription and a granted Discord role, so every payment provider (PayPal,
NOWPayments, future providers) drives the same activation path.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Guild, Payment, Subscription, SubscriptionTier, TierRoleMapping, User, WebhookEvent
from app.models.enums import PaymentProvider as PaymentProviderName
from app.models.enums import PaymentStatus, SubscriptionStatus
from app.services import bot_client
from app.services.payments.base import ParsedWebhookEvent, PaymentProvider, WebhookVerificationError

logger = logging.getLogger(__name__)


class SubscriptionActivationError(Exception):
    """Raised when a confirmed payment cannot be applied to a subscription."""


async def start_checkout(
    db: AsyncSession,
    *,
    user: User,
    tier: SubscriptionTier,
    provider: PaymentProvider,
) -> tuple[Payment, str]:
    """Create a pending subscription + payment row and start a provider checkout.

    Returns the persisted `Payment` and the provider's checkout URL.
    """
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        user_id=user.id,
        tier_id=tier.id,
        status=SubscriptionStatus.PENDING,
        starts_at=now,
        expires_at=now,
    )
    db.add(subscription)
    await db.flush()

    reference = str(subscription.id)
    created = await provider.create_payment(
        amount=float(tier.price),
        currency=tier.currency,
        reference=reference,
        description=f"{tier.name} subscription",
    )

    payment = Payment(
        user_id=user.id,
        subscription_id=subscription.id,
        provider=provider.name,
        payment_method=provider.name.value.lower(),
        amount=tier.price,
        currency=tier.currency,
        provider_transaction_id=created.provider_transaction_id,
        payment_reference=reference,
        invoice_url=created.checkout_url,
        provider_payload=created.raw_payload,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment, created.checkout_url


async def activate_subscription(db: AsyncSession, payment: Payment) -> Subscription:
    """Mark `payment` paid, activate/extend its subscription, and grant the Discord role."""
    if payment.subscription_id is None:
        raise SubscriptionActivationError(f"Payment {payment.id} has no linked subscription")

    subscription = await db.get(Subscription, payment.subscription_id)
    if subscription is None:
        raise SubscriptionActivationError(f"Payment {payment.id} has no linked subscription")

    tier = await db.get(SubscriptionTier, subscription.tier_id)
    if tier is None:
        raise SubscriptionActivationError(f"Subscription {subscription.id} has no tier")

    now = datetime.now(timezone.utc)
    still_active = subscription.status == SubscriptionStatus.ACTIVE and subscription.expires_at > now
    base = subscription.expires_at if still_active else now

    subscription.status = SubscriptionStatus.ACTIVE
    subscription.starts_at = subscription.starts_at or now
    subscription.expires_at = base + timedelta(days=tier.duration_days)

    payment.status = PaymentStatus.PAID
    payment.paid_at = now
    await db.flush()

    mapping_result = await db.execute(
        select(TierRoleMapping).where(TierRoleMapping.tier_id == tier.id)
    )
    mapping = mapping_result.scalar_one_or_none()
    guild = await db.get(Guild, tier.guild_id)
    user = await db.get(User, subscription.user_id)

    if mapping and guild and user:
        await bot_client.assign_role(guild.guild_id, user.discord_id, mapping.discord_role_id)
    else:
        logger.warning(
            "Skipping role assignment for subscription %s: missing tier role mapping, guild, or user",
            subscription.id,
        )

    return subscription


async def record_and_apply_webhook_event(
    db: AsyncSession,
    provider_name: PaymentProviderName,
    event: ParsedWebhookEvent,
) -> WebhookEvent:
    """Persist a verified webhook event (idempotently) and activate the subscription if it paid."""
    existing = await db.execute(
        select(WebhookEvent).where(WebhookEvent.provider_event_id == event.provider_event_id)
    )
    webhook_row = existing.scalar_one_or_none()
    if webhook_row is not None and webhook_row.processed:
        return webhook_row

    if webhook_row is None:
        webhook_row = WebhookEvent(
            provider=provider_name,
            provider_event_id=event.provider_event_id,
            event_type=event.event_type,
            payload=event.raw_payload,
            processed=False,
        )
        db.add(webhook_row)
        await db.flush()

    if event.status == PaymentStatus.PAID:
        payment_result = await db.execute(
            select(Payment).where(Payment.provider_transaction_id == event.provider_transaction_id)
        )
        payment = payment_result.scalar_one_or_none()
        if payment is None:
            webhook_row.error_message = f"No payment found for transaction {event.provider_transaction_id}"
            logger.warning(
                "Webhook %s references unknown transaction %s",
                event.provider_event_id,
                event.provider_transaction_id,
            )
        elif payment.status != PaymentStatus.PAID:
            await activate_subscription(db, payment)

    webhook_row.processed = True
    webhook_row.processed_at = datetime.now(timezone.utc)
    await db.commit()
    return webhook_row


async def process_webhook(
    db: AsyncSession,
    provider: PaymentProvider,
    headers: dict[str, str],
    body: bytes,
) -> WebhookEvent:
    """Verify, parse, and apply an inbound payment-provider webhook end to end."""
    if not await provider.verify_webhook(headers, body):
        raise WebhookVerificationError("Invalid webhook signature")

    event = provider.parse_webhook_event(headers, body)
    return await record_and_apply_webhook_event(db, provider.name, event)
