"""Stripe Checkout Sessions integration.

Uses a one-time ("payment" mode) Checkout Session per billing cycle, not Stripe's
native recurring subscriptions — this keeps Stripe consistent with PayPal and
NOWPayments, where `subscription_service` (not the provider) owns renewal/expiry
via the scheduled job in `app.jobs.expire_subscriptions`.
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.enums import PaymentProvider as PaymentProviderName
from app.models.enums import PaymentStatus
from app.services.payments.base import CreatedPayment, ParsedWebhookEvent, PaymentProvider

logger = logging.getLogger(__name__)

CHECKOUT_COMPLETED_EVENT = "checkout.session.completed"
CHECKOUT_EXPIRED_EVENT = "checkout.session.expired"

_EVENT_STATUS_MAP = {
    CHECKOUT_COMPLETED_EVENT: PaymentStatus.PAID,
    CHECKOUT_EXPIRED_EVENT: PaymentStatus.EXPIRED,
}

# Stripe's own tolerance recommendation for clock drift between the webhook
# timestamp and receipt time, beyond which a signature is treated as a replay.
SIGNATURE_TOLERANCE_SECONDS = 300


class StripeAPIError(Exception):
    """Raised when a call to the Stripe REST API fails."""


class StripeProvider(PaymentProvider):
    name = PaymentProviderName.STRIPE

    def __init__(self) -> None:
        settings = get_settings()
        self._secret_key = settings.stripe_secret_key
        self._webhook_secret = settings.stripe_webhook_secret
        self._base_url = "https://api.stripe.com/v1"
        self._success_url = f"{settings.frontend_base_url}/checkout/success"
        self._cancel_url = f"{settings.frontend_base_url}/checkout/cancel"

    async def create_payment(
        self, *, amount: float, currency: str, reference: str, description: str
    ) -> CreatedPayment:
        # Stripe Checkout takes amounts in the currency's smallest unit (cents for
        # USD), unlike PayPal/NOWPayments which take a decimal amount.
        unit_amount = round(amount * 100)
        form_payload = {
            "mode": "payment",
            "client_reference_id": reference,
            "success_url": self._success_url,
            "cancel_url": self._cancel_url,
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][unit_amount]": str(unit_amount),
            "line_items[0][price_data][product_data][name]": description,
            "metadata[reference]": reference,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/checkout/sessions",
                data=form_payload,
                auth=(self._secret_key, ""),
            )
        if response.status_code not in (200, 201):
            raise StripeAPIError(f"Failed to create Stripe checkout session: {response.text}")

        session = response.json()
        checkout_url = session.get("url")
        if not checkout_url:
            raise StripeAPIError("Stripe checkout session response is missing url")

        return CreatedPayment(
            provider_transaction_id=session["id"],
            checkout_url=checkout_url,
            raw_payload=session,
        )

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool:
        """Verify per Stripe's documented scheme: HMAC-SHA256 of `{timestamp}.{body}`."""
        if not self._webhook_secret:
            logger.error("STRIPE_WEBHOOK_SECRET is not configured; refusing to trust webhook")
            return False

        lower_headers = {key.lower(): value for key, value in headers.items()}
        signature_header = lower_headers.get("stripe-signature")
        if not signature_header:
            return False

        timestamp: str | None = None
        signatures: list[str] = []
        for part in signature_header.split(","):
            key, _, value = part.partition("=")
            if key == "t":
                timestamp = value
            elif key == "v1":
                signatures.append(value)

        if timestamp is None or not signatures:
            return False
        try:
            if abs(time.time() - int(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
                return False
        except ValueError:
            return False

        signed_payload = f"{timestamp}.".encode() + body
        expected = hmac.new(
            self._webhook_secret.encode(), signed_payload, hashlib.sha256
        ).hexdigest()

        return any(hmac.compare_digest(expected, signature) for signature in signatures)

    def parse_webhook_event(self, headers: dict[str, str], body: bytes) -> ParsedWebhookEvent:
        data: dict[str, Any] = json.loads(body)
        event_type = data.get("type", "unknown")
        session = data.get("data", {}).get("object", {})

        return ParsedWebhookEvent(
            provider_event_id=data["id"],
            event_type=event_type,
            provider_transaction_id=session.get("id", ""),
            status=_EVENT_STATUS_MAP.get(event_type, PaymentStatus.PENDING),
            raw_payload=data,
        )
