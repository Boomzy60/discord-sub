"""Provider-agnostic payment interface.

Any payment method (PayPal, NOWPayments, and future providers like Alipay or
WeChat Pay) implements this interface so `subscription_service` can activate
subscriptions without knowing which provider was used.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.models.enums import PaymentProvider as PaymentProviderName
from app.models.enums import PaymentStatus


class WebhookVerificationError(Exception):
    """Raised when an inbound webhook's signature cannot be verified."""


@dataclass(frozen=True)
class CreatedPayment:
    """Result of starting a checkout with a provider."""

    provider_transaction_id: str
    checkout_url: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class ParsedWebhookEvent:
    """A provider webhook payload normalized to the fields subscription_service needs."""

    provider_event_id: str
    event_type: str
    provider_transaction_id: str
    status: PaymentStatus
    raw_payload: dict[str, Any]


class PaymentProvider(ABC):
    """Interface every payment provider integration must implement."""

    name: PaymentProviderName

    @abstractmethod
    async def create_payment(
        self, *, amount: float, currency: str, reference: str, description: str
    ) -> CreatedPayment:
        """Start a checkout for `amount` `currency`, tagged with our `reference`."""

    @abstractmethod
    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool:
        """Return True only if `body` is an authentic, unmodified webhook from this provider."""

    @abstractmethod
    def parse_webhook_event(self, headers: dict[str, str], body: bytes) -> ParsedWebhookEvent:
        """Normalize an already-verified webhook payload."""
