# Payment Provider Abstraction Layer (Milestone 8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provider-agnostic payment interface and a subscription activation service so PayPal, NOWPayments, and future providers plug in without rearchitecting, proven by unit tests against a fake in-memory provider.

**Architecture:** `app/services/payments/base.py` defines the contracts every concrete payment provider implements (`create_payment`, `verify_webhook`, `parse_webhook_event`). `app/services/subscription_service.py` owns subscription lifecycle business logic — `initiate_subscription` (checkout time) and `activate_subscription` (payment-confirmed time) — and depends only on `BasePaymentProvider` and a small `RoleAssignmentClient` `Protocol` it defines, never on a concrete provider or the real Discord bot client. Tests exercise both against fakes.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async ORM (`AsyncSession`), Pydantic/dataclasses, pytest with `asyncio_mode = "auto"`, in-memory SQLite for tests.

## Global Constraints

- Never activate subscriptions before payment confirmation (CLAUDE.md security principle) — `activate_subscription` is the only code path that flips a subscription to `ACTIVE`, and only after marking the payment `PAID`.
- Use UUID primary keys, store Discord IDs as strings, use UTC timestamps (CLAUDE.md) — already enforced by existing models; new code must not bypass them (e.g. always use `datetime.now(timezone.utc)`, never naive datetimes).
- Business logic belongs in services, not routes (CLAUDE.md) — no route files are touched in this plan; that's M9/M10.
- Keep business logic separate from the bot — `RoleAssignmentClient` is an interface; this plan never calls Discord directly.
- Follow existing repo conventions: async SQLAlchemy with `expire_on_commit=False`, `{"success", "data", "error"}` response envelope (not touched here since there are no routes), existing `db_session` pytest fixture in `backend/tests/conftest.py`.

---

### Task 1: Payment provider contracts (`base.py`)

**Files:**
- Create: `backend/app/services/payments/__init__.py`
- Create: `backend/app/services/payments/base.py`
- Test: `backend/tests/test_payments_base.py`

**Interfaces:**
- Produces: `CheckoutRequest(amount: float, currency: str, reference: str, metadata: dict[str, str])`, `CheckoutResult(provider_transaction_id: str, checkout_url: str, raw: dict | None = None)`, `ParsedWebhookEvent(provider_event_id: str, provider_transaction_id: str, event_type: str, status: PaymentStatus, raw_payload: dict)`, `BasePaymentProvider` (ABC) with class attribute `provider_name: PaymentProvider` and abstract async methods `create_payment(request: CheckoutRequest) -> CheckoutResult`, `verify_webhook(headers: Mapping[str, str], body: bytes) -> bool`, `parse_webhook_event(headers: Mapping[str, str], body: bytes) -> ParsedWebhookEvent`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_payments_base.py`:

```python
import pytest

from app.models.enums import PaymentProvider, PaymentStatus
from app.services.payments.base import (
    BasePaymentProvider,
    CheckoutRequest,
    CheckoutResult,
    ParsedWebhookEvent,
)


def test_base_payment_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BasePaymentProvider()


def test_conforming_subclass_can_be_instantiated_and_used():
    class DummyProvider(BasePaymentProvider):
        provider_name = PaymentProvider.PAYPAL

        async def create_payment(self, request: CheckoutRequest) -> CheckoutResult:
            return CheckoutResult(
                provider_transaction_id="dummy-1",
                checkout_url="https://example.com/pay",
            )

        async def verify_webhook(self, headers, body) -> bool:
            return True

        async def parse_webhook_event(self, headers, body) -> ParsedWebhookEvent:
            return ParsedWebhookEvent(
                provider_event_id="evt-1",
                provider_transaction_id="dummy-1",
                event_type="payment.completed",
                status=PaymentStatus.PAID,
                raw_payload={},
            )

    provider = DummyProvider()
    assert provider.provider_name == PaymentProvider.PAYPAL


async def test_checkout_request_defaults_to_empty_metadata():
    request = CheckoutRequest(amount=9.99, currency="USD", reference="ref-1")
    assert request.metadata == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_payments_base.py -v`
Expected: FAIL / collection error — `ModuleNotFoundError: No module named 'app.services.payments'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/payments/__init__.py` (empty file).

Create `backend/app/services/payments/base.py`:

```python
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.models.enums import PaymentProvider, PaymentStatus


@dataclass
class CheckoutRequest:
    """What a payment provider needs to start a checkout/invoice."""

    amount: float
    currency: str
    reference: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class CheckoutResult:
    """What a payment provider returns after starting a checkout/invoice."""

    provider_transaction_id: str
    checkout_url: str
    raw: dict | None = None


@dataclass
class ParsedWebhookEvent:
    """A payment provider's webhook payload, normalized to a common shape."""

    provider_event_id: str
    provider_transaction_id: str
    event_type: str
    status: PaymentStatus
    raw_payload: dict


class BasePaymentProvider(ABC):
    """Provider-agnostic interface every payment provider implements.

    Concrete providers (PayPal, NOWPayments, and future Alipay/WeChat) plug
    in by implementing these three methods; no other code should depend on
    a specific provider's SDK or webhook shape.
    """

    provider_name: PaymentProvider

    @abstractmethod
    async def create_payment(self, request: CheckoutRequest) -> CheckoutResult:
        """Start a checkout/invoice with the provider and return how to pay it."""

    @abstractmethod
    async def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        """Verify an inbound webhook's signature. Must be called before parsing."""

    @abstractmethod
    async def parse_webhook_event(
        self, headers: Mapping[str, str], body: bytes
    ) -> ParsedWebhookEvent:
        """Normalize a verified webhook payload into a ParsedWebhookEvent."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_payments_base.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/payments/__init__.py backend/app/services/payments/base.py backend/tests/test_payments_base.py
git commit -m "feat(backend): add provider-agnostic payment contracts"
```

---

### Task 2: Shared test fixtures + `initiate_subscription`

**Files:**
- Modify: `backend/tests/conftest.py`
- Create: `backend/app/services/subscription_service.py`
- Test: `backend/tests/test_subscription_service.py`

**Interfaces:**
- Consumes: `BasePaymentProvider`, `CheckoutRequest`, `CheckoutResult` from `app.services.payments.base` (Task 1). `Guild`, `User`, `SubscriptionTier`, `TierRoleMapping`, `Subscription`, `Payment` from `app.models`; `BillingPeriod`, `PaymentStatus`, `SubscriptionStatus` from `app.models.enums`.
- Produces: pytest fixtures `guild`, `user`, `tier` in `conftest.py` (reused by Task 3 too). `initiate_subscription(db: AsyncSession, *, user: User, tier: SubscriptionTier, provider: BasePaymentProvider) -> tuple[Subscription, Payment, CheckoutResult]` in `subscription_service.py`. `FakePaymentProvider` and `FakeRoleClient` test doubles, plus `payment_provider` / `role_client` fixtures, in `test_subscription_service.py` (reused by Task 3).

- [ ] **Step 1: Add shared fixtures to `conftest.py`**

Modify `backend/tests/conftest.py` — add these imports near the top (alongside the existing ones) and these fixtures at the end of the file:

```python
from app.models import Guild, SubscriptionTier, TierRoleMapping, User
from app.models.enums import BillingPeriod
```

```python
@pytest.fixture
async def guild(db_session):
    guild = Guild(guild_id="998877665544332211", guild_name="Test Server")
    db_session.add(guild)
    await db_session.flush()
    return guild


@pytest.fixture
async def tier(db_session, guild):
    tier = SubscriptionTier(
        guild_id=guild.id,
        name="Gold",
        price=9.99,
        currency="USD",
        billing_period=BillingPeriod.MONTHLY,
        duration_days=30,
    )
    db_session.add(tier)
    await db_session.flush()

    mapping = TierRoleMapping(
        guild_id=guild.id, tier_id=tier.id, discord_role_id="111222333444555666"
    )
    db_session.add(mapping)
    await db_session.flush()
    await db_session.refresh(tier, ["role_mapping"])
    return tier


@pytest.fixture
async def user(db_session):
    user = User(discord_id="123456789012345678", username="testuser")
    db_session.add(user)
    await db_session.flush()
    return user
```

The full file should now read:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import models  # noqa: F401 ensures all models are registered on Base.metadata
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Guild, SubscriptionTier, TierRoleMapping, User
from app.models.enums import BillingPeriod


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def guild(db_session):
    guild = Guild(guild_id="998877665544332211", guild_name="Test Server")
    db_session.add(guild)
    await db_session.flush()
    return guild


@pytest.fixture
async def tier(db_session, guild):
    tier = SubscriptionTier(
        guild_id=guild.id,
        name="Gold",
        price=9.99,
        currency="USD",
        billing_period=BillingPeriod.MONTHLY,
        duration_days=30,
    )
    db_session.add(tier)
    await db_session.flush()

    mapping = TierRoleMapping(
        guild_id=guild.id, tier_id=tier.id, discord_role_id="111222333444555666"
    )
    db_session.add(mapping)
    await db_session.flush()
    await db_session.refresh(tier, ["role_mapping"])
    return tier


@pytest.fixture
async def user(db_session):
    user = User(discord_id="123456789012345678", username="testuser")
    db_session.add(user)
    await db_session.flush()
    return user
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_subscription_service.py`:

```python
import pytest

from app.models.enums import PaymentProvider, PaymentStatus, SubscriptionStatus
from app.services.payments.base import (
    BasePaymentProvider,
    CheckoutRequest,
    CheckoutResult,
    ParsedWebhookEvent,
)
from app.services.subscription_service import initiate_subscription


class FakePaymentProvider(BasePaymentProvider):
    provider_name = PaymentProvider.PAYPAL

    def __init__(self) -> None:
        self.created_requests: list[CheckoutRequest] = []
        self._next_transaction_id = 1

    async def create_payment(self, request: CheckoutRequest) -> CheckoutResult:
        self.created_requests.append(request)
        transaction_id = f"fake-txn-{self._next_transaction_id}"
        self._next_transaction_id += 1
        return CheckoutResult(
            provider_transaction_id=transaction_id,
            checkout_url=f"https://fake-pay.test/{transaction_id}",
        )

    async def verify_webhook(self, headers, body) -> bool:
        return True

    async def parse_webhook_event(self, headers, body) -> ParsedWebhookEvent:
        raise NotImplementedError("not exercised by subscription_service tests")


class FakeRoleClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.assign_calls: list[dict] = []
        self.remove_calls: list[dict] = []

    async def assign_role(
        self, *, guild_discord_id: str, user_discord_id: str, role_discord_id: str
    ) -> None:
        self.assign_calls.append(
            {
                "guild_discord_id": guild_discord_id,
                "user_discord_id": user_discord_id,
                "role_discord_id": role_discord_id,
            }
        )
        if self.fail:
            raise RuntimeError("role assignment failed")

    async def remove_role(
        self, *, guild_discord_id: str, user_discord_id: str, role_discord_id: str
    ) -> None:
        self.remove_calls.append(
            {
                "guild_discord_id": guild_discord_id,
                "user_discord_id": user_discord_id,
                "role_discord_id": role_discord_id,
            }
        )


@pytest.fixture
def payment_provider():
    return FakePaymentProvider()


@pytest.fixture
def role_client():
    return FakeRoleClient()


async def test_initiate_subscription_creates_pending_rows(db_session, user, tier, payment_provider):
    subscription, payment, checkout_result = await initiate_subscription(
        db_session, user=user, tier=tier, provider=payment_provider
    )

    assert subscription.status == SubscriptionStatus.PENDING
    assert subscription.tier_id == tier.id
    assert payment.status == PaymentStatus.PENDING
    assert payment.subscription_id == subscription.id
    assert payment.provider_transaction_id == checkout_result.provider_transaction_id
    assert payment.invoice_url == checkout_result.checkout_url

    assert len(payment_provider.created_requests) == 1
    request = payment_provider.created_requests[0]
    assert request.amount == tier.price
    assert request.currency == tier.currency
    assert request.metadata["user_id"] == str(user.id)
    assert request.metadata["tier_id"] == str(tier.id)
    assert request.metadata["subscription_id"] == str(subscription.id)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_subscription_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.subscription_service'`

- [ ] **Step 4: Write minimal implementation**

Create `backend/app/services/subscription_service.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Payment, Subscription, SubscriptionTier, User
from app.models.enums import PaymentStatus, SubscriptionStatus
from app.services.payments.base import BasePaymentProvider, CheckoutRequest, CheckoutResult


class RoleAssignmentClient(Protocol):
    """What subscription_service needs to mutate Discord role membership.

    Satisfied by a fake in tests; the real HTTP-calling implementation
    (against the bot's internal API) is a later milestone.
    """

    async def assign_role(
        self, *, guild_discord_id: str, user_discord_id: str, role_discord_id: str
    ) -> None: ...

    async def remove_role(
        self, *, guild_discord_id: str, user_discord_id: str, role_discord_id: str
    ) -> None: ...


class PaymentNotFoundError(Exception):
    """Raised when activate_subscription is given an unknown provider transaction id."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def initiate_subscription(
    db: AsyncSession,
    *,
    user: User,
    tier: SubscriptionTier,
    provider: BasePaymentProvider,
) -> tuple[Subscription, Payment, CheckoutResult]:
    """Create a PENDING subscription + payment and start a checkout with `provider`.

    The subscription is never ACTIVE until activate_subscription confirms payment.
    """
    now = _utcnow()
    subscription = Subscription(
        user_id=user.id,
        tier_id=tier.id,
        status=SubscriptionStatus.PENDING,
        starts_at=now,
        expires_at=now,
    )
    db.add(subscription)
    await db.flush()

    checkout_result = await provider.create_payment(
        CheckoutRequest(
            amount=tier.price,
            currency=tier.currency,
            reference=str(subscription.id),
            metadata={
                "subscription_id": str(subscription.id),
                "user_id": str(user.id),
                "tier_id": str(tier.id),
            },
        )
    )

    payment = Payment(
        user_id=user.id,
        subscription_id=subscription.id,
        provider=provider.provider_name,
        payment_method=provider.provider_name.value.lower(),
        amount=tier.price,
        currency=tier.currency,
        provider_transaction_id=checkout_result.provider_transaction_id,
        invoice_url=checkout_result.checkout_url,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(subscription)
    await db.refresh(payment)

    return subscription, payment, checkout_result
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_subscription_service.py tests/test_payments_base.py -v`
Expected: PASS (4 tests total)

- [ ] **Step 6: Commit**

```bash
git add backend/tests/conftest.py backend/app/services/subscription_service.py backend/tests/test_subscription_service.py
git commit -m "feat(backend): add initiate_subscription to subscription_service"
```

---

### Task 3: `activate_subscription` — full activation flow

**Files:**
- Modify: `backend/app/services/subscription_service.py`
- Modify: `backend/tests/test_subscription_service.py`

**Interfaces:**
- Consumes: `RoleAssignmentClient`, `PaymentNotFoundError`, `_utcnow`, `initiate_subscription` (Task 2, same file); `FakePaymentProvider`, `FakeRoleClient`, `payment_provider`, `role_client` fixtures (Task 2, same test file); `guild`, `user`, `tier` fixtures (Task 2, `conftest.py`).
- Produces: `activate_subscription(db: AsyncSession, *, provider_name: PaymentProvider, provider_transaction_id: str, role_client: RoleAssignmentClient) -> Subscription`. This is the function M9/M10's webhook routes will call after verifying and parsing a provider's webhook.

- [ ] **Step 1: Write failing test — first activation**

Append to `backend/tests/test_subscription_service.py`. First, add these imports at the top of the file (alongside the existing ones):

```python
from datetime import timedelta

from sqlalchemy import select

from app.models import AuditLog, Payment, Subscription
from app.models.enums import AuditAction
from app.services.subscription_service import (
    PaymentNotFoundError,
    activate_subscription,
    initiate_subscription,
)
```

(This replaces the earlier `from app.services.subscription_service import initiate_subscription` line from Task 2 — one import line covering all four names.)

Then append this test:

```python
async def test_activate_subscription_first_activation(
    db_session, user, tier, guild, payment_provider, role_client
):
    subscription, payment, checkout_result = await initiate_subscription(
        db_session, user=user, tier=tier, provider=payment_provider
    )

    activated = await activate_subscription(
        db_session,
        provider_name=payment_provider.provider_name,
        provider_transaction_id=checkout_result.provider_transaction_id,
        role_client=role_client,
    )

    assert activated.id == subscription.id
    assert activated.status == SubscriptionStatus.ACTIVE
    expected_expiry = activated.starts_at + timedelta(days=tier.duration_days)
    assert abs((activated.expires_at - expected_expiry).total_seconds()) < 1

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.PAID
    assert payment.paid_at is not None

    assert len(role_client.assign_calls) == 1
    call = role_client.assign_calls[0]
    assert call["guild_discord_id"] == guild.guild_id
    assert call["user_discord_id"] == user.discord_id
    assert call["role_discord_id"] == tier.role_mapping.discord_role_id

    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_id == activated.id)
    )
    actions = {row.action for row in audit_result.scalars().all()}
    assert AuditAction.SUBSCRIPTION_CREATED in actions
    assert AuditAction.ROLE_ASSIGNED in actions
```

- [ ] **Step 2: Write failing test — renewal extends from current expiry**

Append:

```python
async def test_activate_subscription_renewal_extends_from_current_expiry(
    db_session, user, tier, guild, payment_provider, role_client
):
    _, _, first_checkout = await initiate_subscription(
        db_session, user=user, tier=tier, provider=payment_provider
    )
    first_activation = await activate_subscription(
        db_session,
        provider_name=payment_provider.provider_name,
        provider_transaction_id=first_checkout.provider_transaction_id,
        role_client=role_client,
    )
    first_expiry = first_activation.expires_at

    renewal_payment = Payment(
        user_id=user.id,
        subscription_id=first_activation.id,
        provider=payment_provider.provider_name,
        payment_method="paypal",
        amount=tier.price,
        currency=tier.currency,
        provider_transaction_id="fake-txn-renewal",
        status=PaymentStatus.PENDING,
    )
    db_session.add(renewal_payment)
    await db_session.commit()

    renewed = await activate_subscription(
        db_session,
        provider_name=payment_provider.provider_name,
        provider_transaction_id="fake-txn-renewal",
        role_client=role_client,
    )

    assert renewed.id == first_activation.id
    expected_expiry = first_expiry + timedelta(days=tier.duration_days)
    assert abs((renewed.expires_at - expected_expiry).total_seconds()) < 1
```

- [ ] **Step 3: Write failing test — idempotent replay retries only the role call**

Append:

```python
async def test_activate_subscription_is_idempotent_but_retries_role_assignment(
    db_session, user, tier, guild, payment_provider, role_client
):
    _, _, checkout_result = await initiate_subscription(
        db_session, user=user, tier=tier, provider=payment_provider
    )

    first = await activate_subscription(
        db_session,
        provider_name=payment_provider.provider_name,
        provider_transaction_id=checkout_result.provider_transaction_id,
        role_client=role_client,
    )
    second = await activate_subscription(
        db_session,
        provider_name=payment_provider.provider_name,
        provider_transaction_id=checkout_result.provider_transaction_id,
        role_client=role_client,
    )

    assert first.expires_at == second.expires_at
    assert len(role_client.assign_calls) == 2

    audit_result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_id == first.id,
            AuditLog.action == AuditAction.SUBSCRIPTION_CREATED,
        )
    )
    assert len(audit_result.scalars().all()) == 1
```

- [ ] **Step 4: Write failing test — unknown transaction id**

Append:

```python
async def test_activate_subscription_raises_for_unknown_transaction_id(
    db_session, role_client, payment_provider
):
    with pytest.raises(PaymentNotFoundError):
        await activate_subscription(
            db_session,
            provider_name=payment_provider.provider_name,
            provider_transaction_id="does-not-exist",
            role_client=role_client,
        )
```

- [ ] **Step 5: Write failing test — role assignment failure still commits payment**

Append:

```python
async def test_activate_subscription_commits_payment_even_if_role_assignment_fails(
    db_session, user, tier, payment_provider
):
    _, payment, checkout_result = await initiate_subscription(
        db_session, user=user, tier=tier, provider=payment_provider
    )
    failing_role_client = FakeRoleClient(fail=True)

    with pytest.raises(RuntimeError):
        await activate_subscription(
            db_session,
            provider_name=payment_provider.provider_name,
            provider_transaction_id=checkout_result.provider_transaction_id,
            role_client=failing_role_client,
        )

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.PAID

    result = await db_session.execute(
        select(Subscription).where(Subscription.id == payment.subscription_id)
    )
    subscription = result.scalar_one()
    assert subscription.status == SubscriptionStatus.ACTIVE
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_subscription_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'activate_subscription' from 'app.services.subscription_service'` (and `PaymentNotFoundError` import, which already exists from Task 2, still resolves fine)

- [ ] **Step 7: Implement `activate_subscription`**

Modify `backend/app/services/subscription_service.py`. Change the imports at the top from:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Payment, Subscription, SubscriptionTier, User
from app.models.enums import PaymentStatus, SubscriptionStatus
from app.services.payments.base import BasePaymentProvider, CheckoutRequest, CheckoutResult
```

to:

```python
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditLog, Payment, Subscription, SubscriptionTier, User
from app.models.enums import AuditAction, PaymentProvider, PaymentStatus, SubscriptionStatus
from app.services.payments.base import BasePaymentProvider, CheckoutRequest, CheckoutResult
```

Then append these functions at the end of the file (after `initiate_subscription`):

```python
async def _load_payment_for_activation(
    db: AsyncSession, *, provider_name: PaymentProvider, provider_transaction_id: str
) -> Payment | None:
    result = await db.execute(
        select(Payment)
        .options(
            selectinload(Payment.subscription)
            .selectinload(Subscription.tier)
            .selectinload(SubscriptionTier.role_mapping),
            selectinload(Payment.subscription)
            .selectinload(Subscription.tier)
            .selectinload(SubscriptionTier.guild),
            selectinload(Payment.subscription).selectinload(Subscription.user),
        )
        .where(
            Payment.provider == provider_name,
            Payment.provider_transaction_id == provider_transaction_id,
        )
    )
    return result.scalar_one_or_none()


def _log_audit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: AuditAction,
    entity_type: str,
    entity_id: uuid.UUID,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )


async def activate_subscription(
    db: AsyncSession,
    *,
    provider_name: PaymentProvider,
    provider_transaction_id: str,
    role_client: RoleAssignmentClient,
) -> Subscription:
    """Confirm a payment and activate its subscription, assigning the Discord role.

    Safe to call more than once for the same provider_transaction_id (e.g. a
    webhook redelivery): the payment/subscription mutation only happens once,
    but the role assignment call is always retried so a prior failure there
    can self-heal on the next delivery.
    """
    payment = await _load_payment_for_activation(
        db, provider_name=provider_name, provider_transaction_id=provider_transaction_id
    )
    if payment is None:
        raise PaymentNotFoundError(
            f"No payment found for provider={provider_name} "
            f"transaction_id={provider_transaction_id}"
        )

    subscription = payment.subscription
    tier = subscription.tier
    role_mapping = tier.role_mapping
    guild = tier.guild
    user = subscription.user

    if payment.status != PaymentStatus.PAID:
        now = _utcnow()
        if subscription.status == SubscriptionStatus.ACTIVE and subscription.expires_at > now:
            subscription.expires_at = subscription.expires_at + timedelta(days=tier.duration_days)
            action = AuditAction.SUBSCRIPTION_EXTENDED
        else:
            subscription.starts_at = now
            subscription.expires_at = now + timedelta(days=tier.duration_days)
            action = AuditAction.SUBSCRIPTION_CREATED
        subscription.status = SubscriptionStatus.ACTIVE

        payment.status = PaymentStatus.PAID
        payment.paid_at = now

        _log_audit(
            db,
            user_id=user.id,
            action=AuditAction.PAYMENT_RECEIVED,
            entity_type="payment",
            entity_id=payment.id,
        )
        _log_audit(
            db, user_id=user.id, action=action, entity_type="subscription", entity_id=subscription.id
        )

        await db.commit()
        await db.refresh(subscription)
        await db.refresh(payment)

    await role_client.assign_role(
        guild_discord_id=guild.guild_id,
        user_discord_id=user.discord_id,
        role_discord_id=role_mapping.discord_role_id,
    )
    _log_audit(
        db,
        user_id=user.id,
        action=AuditAction.ROLE_ASSIGNED,
        entity_type="subscription",
        entity_id=subscription.id,
    )
    await db.commit()

    return subscription
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_subscription_service.py tests/test_payments_base.py -v`
Expected: PASS (9 tests total)

- [ ] **Step 9: Run the full backend test suite to check for regressions**

Run: `cd backend && python -m pytest -v`
Expected: PASS (all existing tests plus the 9 new ones)

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/subscription_service.py backend/tests/test_subscription_service.py
git commit -m "feat(backend): add activate_subscription with idempotent role assignment"
```

---

## Self-Review Notes

- **Spec coverage:** `base.py` contracts (Task 1), `RoleAssignmentClient` protocol + `PaymentNotFoundError` + `initiate_subscription` (Task 2), full `activate_subscription` flow including renewal extension, idempotent replay, not-found, and role-failure-still-commits (Task 3) all map directly to the design spec's four numbered sections. Guild/tier/user test fixtures needed by the spec's test plan are added in Task 2 so Task 3 can reuse them.
- **Type consistency:** `RoleAssignmentClient.assign_role`/`remove_role` signatures match between the Task 2 protocol definition and the Task 2 `FakeRoleClient` test double and Task 3's real call site. `activate_subscription`'s parameter names (`provider_name`, `provider_transaction_id`, `role_client`) are consistent across Task 3's five test call sites and the Task 3 implementation. `CheckoutRequest`/`CheckoutResult` field names match between Task 1's definition and Task 2's `initiate_subscription`/`FakePaymentProvider` usage.
- **Note on spec's `Decimal` mention:** the design spec's prose used `Decimal` for `CheckoutRequest.amount`; this plan uses `float` to match the existing `SubscriptionTier.price: Mapped[float]` and `Payment.amount: Mapped[float]` columns, avoiding a type mismatch with the rest of the codebase. This is a minor implementation detail, not a behavior change.
