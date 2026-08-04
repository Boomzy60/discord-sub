import json

import respx
from httpx import Response

from app.core.config import get_settings
from app.models.enums import PaymentStatus
from app.services.payments.paypal import (
    CAPTURE_COMPLETED_EVENT,
    ORDER_APPROVED_EVENT,
    PayPalAPIError,
    PayPalProvider,
)

settings = get_settings()
BASE_URL = "https://api-m.sandbox.paypal.com"


def _mock_token():
    respx.post(f"{BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "sandbox-token", "token_type": "Bearer"})
    )


@respx.mock
async def test_create_payment_returns_approval_link_and_order_id():
    _mock_token()
    respx.post(f"{BASE_URL}/v2/checkout/orders").mock(
        return_value=Response(
            201,
            json={
                "id": "ORDER123",
                "links": [
                    {"rel": "self", "href": "https://api.paypal.com/v2/checkout/orders/ORDER123"},
                    {"rel": "approve", "href": "https://paypal.com/checkoutnow?token=ORDER123"},
                ],
            },
        )
    )

    provider = PayPalProvider()
    created = await provider.create_payment(
        amount=9.99, currency="USD", reference="ref-1", description="Gold subscription"
    )

    assert created.provider_transaction_id == "ORDER123"
    assert created.checkout_url == "https://paypal.com/checkoutnow?token=ORDER123"


@respx.mock
async def test_create_payment_raises_when_order_creation_fails():
    _mock_token()
    respx.post(f"{BASE_URL}/v2/checkout/orders").mock(return_value=Response(400, json={"error": "bad"}))

    provider = PayPalProvider()
    try:
        await provider.create_payment(amount=1, currency="USD", reference="r", description="d")
        assert False, "expected PayPalAPIError"
    except PayPalAPIError:
        pass


@respx.mock
async def test_verify_webhook_returns_true_on_success_status():
    _mock_token()
    respx.post(f"{BASE_URL}/v1/notifications/verify-webhook-signature").mock(
        return_value=Response(200, json={"verification_status": "SUCCESS"})
    )

    provider = PayPalProvider()
    provider._webhook_id = "wh-1"
    headers = {
        "paypal-transmission-id": "tx-1",
        "paypal-transmission-time": "2026-01-01T00:00:00Z",
        "paypal-cert-url": "https://api.paypal.com/cert",
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-transmission-sig": "sig",
    }
    body = json.dumps({"id": "evt-1", "event_type": CAPTURE_COMPLETED_EVENT}).encode()

    assert await provider.verify_webhook(headers, body) is True


@respx.mock
async def test_verify_webhook_returns_false_on_failure_status():
    _mock_token()
    respx.post(f"{BASE_URL}/v1/notifications/verify-webhook-signature").mock(
        return_value=Response(200, json={"verification_status": "FAILURE"})
    )

    provider = PayPalProvider()
    provider._webhook_id = "wh-1"
    headers = {
        "paypal-transmission-id": "tx-1",
        "paypal-transmission-time": "2026-01-01T00:00:00Z",
        "paypal-cert-url": "https://api.paypal.com/cert",
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-transmission-sig": "sig",
    }
    body = json.dumps({"id": "evt-1", "event_type": CAPTURE_COMPLETED_EVENT}).encode()

    assert await provider.verify_webhook(headers, body) is False


async def test_verify_webhook_returns_false_when_headers_missing():
    provider = PayPalProvider()
    assert await provider.verify_webhook({}, b"{}") is False


def test_parse_webhook_event_maps_capture_completed_to_paid():
    provider = PayPalProvider()
    body = json.dumps(
        {
            "id": "evt-1",
            "event_type": CAPTURE_COMPLETED_EVENT,
            "resource": {
                "id": "CAPTURE1",
                "custom_id": "ref-1",
                "supplementary_data": {"related_ids": {"order_id": "ORDER123"}},
            },
        }
    ).encode()

    event = provider.parse_webhook_event({}, body)

    assert event.provider_event_id == "evt-1"
    assert event.status == PaymentStatus.PAID
    assert event.provider_transaction_id == "ORDER123"


def test_parse_webhook_event_defaults_unmapped_events_to_pending():
    provider = PayPalProvider()
    body = json.dumps(
        {"id": "evt-2", "event_type": ORDER_APPROVED_EVENT, "resource": {"id": "ORDER123"}}
    ).encode()

    event = provider.parse_webhook_event({}, body)

    assert event.status == PaymentStatus.PENDING
    assert event.provider_transaction_id == "ORDER123"
