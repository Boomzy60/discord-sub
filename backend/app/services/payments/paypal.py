"""PayPal REST API v2 integration (Orders + Webhooks)."""

import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.enums import PaymentProvider as PaymentProviderName
from app.models.enums import PaymentStatus
from app.services.payments.base import CreatedPayment, ParsedWebhookEvent, PaymentProvider

logger = logging.getLogger(__name__)

ORDER_APPROVED_EVENT = "CHECKOUT.ORDER.APPROVED"
CAPTURE_COMPLETED_EVENT = "PAYMENT.CAPTURE.COMPLETED"
CAPTURE_DENIED_EVENT = "PAYMENT.CAPTURE.DENIED"

_EVENT_STATUS_MAP = {
    CAPTURE_COMPLETED_EVENT: PaymentStatus.PAID,
    CAPTURE_DENIED_EVENT: PaymentStatus.FAILED,
}

_TRANSMISSION_HEADERS = (
    "paypal-transmission-id",
    "paypal-transmission-time",
    "paypal-cert-url",
    "paypal-auth-algo",
    "paypal-transmission-sig",
)


class PayPalAPIError(Exception):
    """Raised when a call to the PayPal REST API fails."""


class PayPalProvider(PaymentProvider):
    name = PaymentProviderName.PAYPAL

    def __init__(self) -> None:
        settings = get_settings()
        self._client_id = settings.paypal_client_id
        self._client_secret = settings.paypal_client_secret
        self._webhook_id = settings.paypal_webhook_id
        self._base_url = (
            "https://api-m.paypal.com"
            if settings.paypal_mode == "live"
            else "https://api-m.sandbox.paypal.com"
        )
        self._return_url = f"{settings.frontend_base_url}/checkout/success"
        self._cancel_url = f"{settings.frontend_base_url}/checkout/cancel"

    async def _get_access_token(self) -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
            )
        if response.status_code != 200:
            raise PayPalAPIError(f"Failed to obtain PayPal access token: {response.text}")
        return response.json()["access_token"]

    async def create_payment(
        self, *, amount: float, currency: str, reference: str, description: str
    ) -> CreatedPayment:
        token = await self._get_access_token()
        order_payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": reference,
                    "custom_id": reference,
                    "description": description,
                    "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
                }
            ],
            "application_context": {
                "return_url": self._return_url,
                "cancel_url": self._cancel_url,
                "user_action": "PAY_NOW",
            },
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/v2/checkout/orders",
                json=order_payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code not in (200, 201):
            raise PayPalAPIError(f"Failed to create PayPal order: {response.text}")

        order = response.json()
        approve_link = next(
            (link["href"] for link in order.get("links", []) if link.get("rel") == "approve"),
            None,
        )
        if approve_link is None:
            raise PayPalAPIError("PayPal order response is missing an approval link")

        return CreatedPayment(
            provider_transaction_id=order["id"],
            checkout_url=approve_link,
            raw_payload=order,
        )

    async def capture_order(self, order_id: str) -> dict[str, Any]:
        """Capture a buyer-approved PayPal order, triggering PAYMENT.CAPTURE.COMPLETED."""
        token = await self._get_access_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/v2/checkout/orders/{order_id}/capture",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code not in (200, 201):
            raise PayPalAPIError(f"Failed to capture PayPal order {order_id}: {response.text}")
        return response.json()

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool:
        """Verify signature via PayPal's verify-webhook-signature API (their recommended approach)."""
        if not self._webhook_id:
            logger.error("PAYPAL_WEBHOOK_ID is not configured; refusing to trust webhook")
            return False

        lower_headers = {key.lower(): value for key, value in headers.items()}
        if any(lower_headers.get(header) is None for header in _TRANSMISSION_HEADERS):
            return False

        token = await self._get_access_token()
        verify_payload = {
            "transmission_id": lower_headers["paypal-transmission-id"],
            "transmission_time": lower_headers["paypal-transmission-time"],
            "cert_url": lower_headers["paypal-cert-url"],
            "auth_algo": lower_headers["paypal-auth-algo"],
            "transmission_sig": lower_headers["paypal-transmission-sig"],
            "webhook_id": self._webhook_id,
            "webhook_event": json.loads(body),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/v1/notifications/verify-webhook-signature",
                json=verify_payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code != 200:
            logger.error("PayPal webhook verification call failed: %s", response.text)
            return False

        return response.json().get("verification_status") == "SUCCESS"

    def parse_webhook_event(self, headers: dict[str, str], body: bytes) -> ParsedWebhookEvent:
        data = json.loads(body)
        event_type = data.get("event_type", "UNKNOWN")
        resource = data.get("resource", {})

        provider_transaction_id = (
            resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
            or resource.get("custom_id")
            or resource.get("id", "")
        )

        return ParsedWebhookEvent(
            provider_event_id=data["id"],
            event_type=event_type,
            provider_transaction_id=provider_transaction_id,
            status=_EVENT_STATUS_MAP.get(event_type, PaymentStatus.PENDING),
            raw_payload=data,
        )
