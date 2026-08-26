import hashlib
import hmac
import json

import respx
from httpx import Response

from app.core.config import get_settings
from app.models.enums import PaymentStatus
from app.services.payments.nowpayments import NOWPaymentsAPIError, NOWPaymentsProvider

settings = get_settings()
BASE_URL = "https://api.nowpayments.io/v1"


@respx.mock
async def test_create_payment_returns_invoice_url_and_uses_reference_as_transaction_id():
    respx.post(f"{BASE_URL}/invoice").mock(
        return_value=Response(
            201,
            json={"id": "INV123", "invoice_url": "https://nowpayments.io/payment/INV123"},
        )
    )

    provider = NOWPaymentsProvider()
    created = await provider.create_payment(
        amount=9.99, currency="usd", reference="order-ref-1", description="Gold subscription"
    )

    assert created.checkout_url == "https://nowpayments.io/payment/INV123"
    assert created.provider_transaction_id == "order-ref-1"


@respx.mock
async def test_create_payment_raises_on_api_failure():
    respx.post(f"{BASE_URL}/invoice").mock(return_value=Response(400, json={"error": "bad"}))

    provider = NOWPaymentsProvider()
    try:
        await provider.create_payment(amount=1, currency="usd", reference="r", description="d")
        assert False, "expected NOWPaymentsAPIError"
    except NOWPaymentsAPIError:
        pass


def _sign(payload: dict, secret: str) -> str:
    sorted_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(secret.encode(), sorted_payload.encode(), hashlib.sha512).hexdigest()


async def test_verify_webhook_accepts_valid_signature():
    provider = NOWPaymentsProvider()
    provider._ipn_secret = "test-secret"
    payload = {"payment_id": 1, "payment_status": "finished", "order_id": "order-ref-1"}
    signature = _sign(payload, "test-secret")
    body = json.dumps(payload).encode()

    assert await provider.verify_webhook({"x-nowpayments-sig": signature}, body) is True


async def test_verify_webhook_rejects_invalid_signature():
    provider = NOWPaymentsProvider()
    provider._ipn_secret = "test-secret"
    payload = {"payment_id": 1, "payment_status": "finished", "order_id": "order-ref-1"}
    body = json.dumps(payload).encode()

    assert await provider.verify_webhook({"x-nowpayments-sig": "wrong"}, body) is False


async def test_verify_webhook_rejects_missing_signature_header():
    provider = NOWPaymentsProvider()
    provider._ipn_secret = "test-secret"

    assert await provider.verify_webhook({}, b"{}") is False


def test_parse_webhook_event_maps_finished_to_paid():
    provider = NOWPaymentsProvider()
    body = json.dumps(
        {"payment_id": 1, "payment_status": "finished", "order_id": "order-ref-1"}
    ).encode()

    event = provider.parse_webhook_event({}, body)

    assert event.status == PaymentStatus.PAID
    assert event.provider_transaction_id == "order-ref-1"
    assert event.provider_event_id == "1:finished"


def test_parse_webhook_event_maps_unknown_status_to_pending():
    provider = NOWPaymentsProvider()
    body = json.dumps(
        {"payment_id": 1, "payment_status": "confirming", "order_id": "order-ref-1"}
    ).encode()

    event = provider.parse_webhook_event({}, body)

    assert event.status == PaymentStatus.PENDING
