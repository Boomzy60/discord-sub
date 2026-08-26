import hashlib
import hmac
import json
import time

import respx
from httpx import Response

from app.core.config import get_settings
from app.models.enums import PaymentStatus
from app.services.payments.stripe_provider import (
    CHECKOUT_COMPLETED_EVENT,
    StripeAPIError,
    StripeProvider,
)

settings = get_settings()
BASE_URL = "https://api.stripe.com/v1"


def _signed_headers(secret: str, body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return {"stripe-signature": f"t={timestamp},v1={signature}"}


@respx.mock
async def test_create_payment_returns_checkout_url_and_session_id():
    respx.post(f"{BASE_URL}/checkout/sessions").mock(
        return_value=Response(
            200,
            json={"id": "cs_test_123", "url": "https://checkout.stripe.com/pay/cs_test_123"},
        )
    )

    provider = StripeProvider()
    created = await provider.create_payment(
        amount=9.99, currency="USD", reference="ref-1", description="Gold subscription"
    )

    assert created.provider_transaction_id == "cs_test_123"
    assert created.checkout_url == "https://checkout.stripe.com/pay/cs_test_123"


@respx.mock
async def test_create_payment_raises_when_session_creation_fails():
    respx.post(f"{BASE_URL}/checkout/sessions").mock(return_value=Response(400, json={"error": "bad"}))

    provider = StripeProvider()
    try:
        await provider.create_payment(amount=1, currency="USD", reference="r", description="d")
        assert False, "expected StripeAPIError"
    except StripeAPIError:
        pass


async def test_verify_webhook_returns_true_for_valid_signature():
    provider = StripeProvider()
    provider._webhook_secret = "whsec_test"
    body = json.dumps({"id": "evt-1", "type": CHECKOUT_COMPLETED_EVENT}).encode()
    headers = _signed_headers("whsec_test", body)

    assert await provider.verify_webhook(headers, body) is True


async def test_verify_webhook_returns_false_for_wrong_secret():
    provider = StripeProvider()
    provider._webhook_secret = "whsec_test"
    body = json.dumps({"id": "evt-1", "type": CHECKOUT_COMPLETED_EVENT}).encode()
    headers = _signed_headers("whsec_other", body)

    assert await provider.verify_webhook(headers, body) is False


async def test_verify_webhook_returns_false_when_secret_not_configured():
    provider = StripeProvider()
    provider._webhook_secret = ""
    body = json.dumps({"id": "evt-1", "type": CHECKOUT_COMPLETED_EVENT}).encode()
    headers = _signed_headers("whsec_test", body)

    assert await provider.verify_webhook(headers, body) is False


async def test_verify_webhook_returns_false_when_header_missing():
    provider = StripeProvider()
    provider._webhook_secret = "whsec_test"

    assert await provider.verify_webhook({}, b"{}") is False


async def test_verify_webhook_returns_false_for_stale_timestamp():
    provider = StripeProvider()
    provider._webhook_secret = "whsec_test"
    body = json.dumps({"id": "evt-1", "type": CHECKOUT_COMPLETED_EVENT}).encode()
    stale_timestamp = str(int(time.time()) - 3600)
    signature = hmac.new(
        b"whsec_test", f"{stale_timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    headers = {"stripe-signature": f"t={stale_timestamp},v1={signature}"}

    assert await provider.verify_webhook(headers, body) is False


def test_parse_webhook_event_maps_checkout_completed_to_paid():
    provider = StripeProvider()
    body = json.dumps(
        {
            "id": "evt-1",
            "type": CHECKOUT_COMPLETED_EVENT,
            "data": {"object": {"id": "cs_test_123"}},
        }
    ).encode()

    event = provider.parse_webhook_event({}, body)

    assert event.provider_event_id == "evt-1"
    assert event.status == PaymentStatus.PAID
    assert event.provider_transaction_id == "cs_test_123"


def test_parse_webhook_event_defaults_unmapped_events_to_pending():
    provider = StripeProvider()
    body = json.dumps(
        {"id": "evt-2", "type": "checkout.session.async_payment_failed", "data": {"object": {"id": "cs_test_123"}}}
    ).encode()

    event = provider.parse_webhook_event({}, body)

    assert event.status == PaymentStatus.PENDING
    assert event.provider_transaction_id == "cs_test_123"
