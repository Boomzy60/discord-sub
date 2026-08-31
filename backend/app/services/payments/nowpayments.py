"""NOWPayments crypto invoice + IPN integration."""

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.enums import PaymentProvider as PaymentProviderName
from app.models.enums import PaymentStatus
from app.services.payments.base import CreatedPayment, ParsedWebhookEvent, PaymentProvider

logger = logging.getLogger(__name__)

IPN_SIGNATURE_HEADER = "x-nowpayments-sig"

_STATUS_MAP = {
    "finished": PaymentStatus.PAID,
    "failed": PaymentStatus.FAILED,
    "expired": PaymentStatus.EXPIRED,
    "refunded": PaymentStatus.REFUNDED,
}

# Curated set of well-known coins presented to the customer, rather than every currency
# enabled on the NOWPayments account (it supports ~350). BTC's real minimum runs far
# above the rest of this list (~$25+ vs ~$11-13 for everything else here), which is why
# `get_available_currencies` still checks live rather than treating this list as safe
# by itself.
SUPPORTED_CURRENCIES: dict[str, str] = {
    "btc": "Bitcoin (BTC)",
    "eth": "Ethereum (ETH)",
    "ltc": "Litecoin (LTC)",
    "trx": "TRON (TRX)",
    "usdttrc20": "USDT (TRC-20)",
    "usdterc20": "USDT (ERC-20)",
    "usdc": "USD Coin (USDC)",
    "xrp": "XRP",
    "doge": "Dogecoin (DOGE)",
    "sol": "Solana (SOL)",
    "bnbbsc": "BNB (BSC)",
    "ton": "Toncoin (TON)",
    "bch": "Bitcoin Cash (BCH)",
    "ada": "Cardano (ADA)",
}


class NOWPaymentsAPIError(Exception):
    """Raised when a call to the NOWPayments REST API fails."""


def _sort_for_signature(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sort_for_signature(value[key]) for key in sorted(value.keys())}
    if isinstance(value, list):
        return [_sort_for_signature(item) for item in value]
    return value


class NOWPaymentsProvider(PaymentProvider):
    name = PaymentProviderName.NOWPAYMENTS

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.nowpayments_api_key
        self._ipn_secret = settings.nowpayments_ipn_secret
        self._base_url = "https://api.nowpayments.io/v1"
        self._ipn_callback_url = f"{settings.backend_base_url}/webhooks/nowpayments"
        self._success_url = f"{settings.frontend_base_url}/checkout/success"
        self._cancel_url = f"{settings.frontend_base_url}/checkout/cancel"

    async def get_available_currencies(
        self, *, amount: float, currency: str
    ) -> list[dict[str, str]]:
        """Return the `SUPPORTED_CURRENCIES` whose NOWPayments minimum payment amount,
        converted to `currency`, is at or below `amount`.

        Presenting every NOWPayments-enabled currency regardless of the tier price leads
        customers straight into a "not up to amount" rejection on NOWPayments' own page
        (BTC in particular runs ~$25+ regardless of tier price), so this is checked live
        rather than assumed from a static list.
        """
        currency = currency.lower()

        async with httpx.AsyncClient(timeout=10.0) as client:
            responses = await asyncio.gather(
                *(
                    client.get(
                        f"{self._base_url}/min-amount",
                        params={
                            "currency_from": code,
                            "currency_to": currency,
                            "fiat_equivalent": currency,
                        },
                        headers={"x-api-key": self._api_key},
                    )
                    for code in SUPPORTED_CURRENCIES
                ),
                return_exceptions=True,
            )

        available: list[dict[str, str]] = []
        for code, response in zip(SUPPORTED_CURRENCIES, responses):
            if isinstance(response, Exception) or response.status_code != 200:
                continue
            min_fiat = response.json().get("fiat_equivalent")
            if min_fiat is not None and min_fiat <= amount:
                available.append({"code": code, "label": SUPPORTED_CURRENCIES[code]})

        return available

    async def create_payment(
        self,
        *,
        amount: float,
        currency: str,
        reference: str,
        description: str,
        pay_currency: str | None = None,
    ) -> CreatedPayment:
        # NOWPayments IPNs always echo back our `order_id`, but not necessarily the
        # invoice `id`, so `reference` (order_id) is what we use to correlate later.
        invoice_payload = {
            "price_amount": amount,
            "price_currency": currency,
            "order_id": reference,
            "order_description": description,
            "ipn_callback_url": self._ipn_callback_url,
            "success_url": self._success_url,
            "cancel_url": self._cancel_url,
        }
        if pay_currency:
            # Locks the hosted invoice to this single currency so NOWPayments' own page
            # can't offer a coin we already know won't clear its minimum for this amount.
            invoice_payload["pay_currency"] = pay_currency

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/invoice",
                json=invoice_payload,
                headers={"x-api-key": self._api_key},
            )
        if response.status_code not in (200, 201):
            raise NOWPaymentsAPIError(f"Failed to create NOWPayments invoice: {response.text}")

        invoice = response.json()
        invoice_url = invoice.get("invoice_url")
        if not invoice_url:
            raise NOWPaymentsAPIError("NOWPayments invoice response is missing invoice_url")

        return CreatedPayment(
            provider_transaction_id=reference,
            checkout_url=invoice_url,
            raw_payload=invoice,
        )

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool:
        if not self._ipn_secret:
            logger.error("NOWPAYMENTS_IPN_SECRET is not configured; refusing to trust webhook")
            return False

        lower_headers = {key.lower(): value for key, value in headers.items()}
        signature = lower_headers.get(IPN_SIGNATURE_HEADER)
        if not signature:
            return False

        data = json.loads(body)
        sorted_payload = json.dumps(_sort_for_signature(data), separators=(",", ":"))
        computed = hmac.new(
            self._ipn_secret.encode(), sorted_payload.encode(), hashlib.sha512
        ).hexdigest()

        return hmac.compare_digest(computed, signature)

    def parse_webhook_event(self, headers: dict[str, str], body: bytes) -> ParsedWebhookEvent:
        data = json.loads(body)
        payment_status = data.get("payment_status", "unknown")
        payment_id = data.get("payment_id")
        order_id = data.get("order_id", "")

        return ParsedWebhookEvent(
            provider_event_id=f"{payment_id}:{payment_status}",
            event_type=payment_status,
            provider_transaction_id=order_id,
            status=_STATUS_MAP.get(payment_status, PaymentStatus.PENDING),
            raw_payload=data,
        )
