# Milestone 8 — Payment Provider Abstraction Layer

## Context

`SubscriptionTier`, `TierRoleMapping`, `Subscription`, `Payment`, `WebhookEvent`, `AuditLog`,
and `Guild` models already exist (from the database-layer milestone). The bot's internal role
API (`bot/app/internal_api.py`, `bot/app/discord_client.py`) is already built and exposes
`POST /internal/roles/assign` / `/remove`, authenticated by a shared secret header.

Two milestones this one nominally depends on/precedes are not fully built yet:

- **M5** (tiers HTTP API — `app/api/routes/tiers.py`, `app/services/subscription_tiers.py`)
  has a design doc but no code.
- **M7**'s backend-side piece (`app/services/bot_client.py`, the HTTP client that calls the
  bot's internal API) doesn't exist yet, though the bot side does.

Decision: M8 proceeds independently of both gaps. It works directly against the existing
`SubscriptionTier` / `TierRoleMapping` models (no HTTP tier API needed), and defines a small
`RoleAssignmentClient` `Protocol` for dependency injection rather than depending on a concrete
bot client. M8's tests use a fake implementation of that protocol; M7 later provides the real
HTTP-based implementation (calling `bot/app/internal_api.py`) that satisfies the same protocol.

## Components

### `app/services/payments/base.py`

Provider-agnostic contracts every payment provider (PayPal, NOWPayments, and future
Alipay/WeChat) implements:

- `CheckoutRequest` (dataclass): `amount: Decimal`, `currency: str`, `reference: str`,
  `metadata: dict[str, str]` — data needed to start a checkout.
- `CheckoutResult` (dataclass): `provider_transaction_id: str`, `checkout_url: str`,
  `raw: dict | None` — what a provider returns after creating a payment/invoice.
- `ParsedWebhookEvent` (dataclass): `provider_event_id: str`, `provider_transaction_id: str`,
  `event_type: str`, `status: PaymentStatus`, `raw_payload: dict` — the normalized shape a
  provider's webhook payload is reduced to.
- `BasePaymentProvider` (ABC): `provider_name: ClassVar[PaymentProvider]` plus three abstract
  async methods — `create_payment(request) -> CheckoutResult`,
  `verify_webhook(headers, body) -> bool`, `parse_webhook_event(headers, body) -> ParsedWebhookEvent`.

Webhook routes (M9/M10) will call `verify_webhook` then `parse_webhook_event`, then hand the
result to `subscription_service.activate_subscription`. Building those routes is out of scope
for M8.

### `app/services/subscription_service.py`

Owns the full subscription lifecycle so M9/M10 checkout and webhook routes don't duplicate
business logic per-provider.

`RoleAssignmentClient` (`Protocol`, defined in this file): `async assign_role(*, guild_discord_id, user_discord_id, role_discord_id) -> None`
and the matching `remove_role`. M8 tests use a fake implementation; the real HTTP-calling
implementation (M7) will satisfy this same protocol against the bot's internal API.

`PaymentNotFoundError(Exception)` — raised when `activate_subscription` is given a
`provider_transaction_id` with no matching `Payment` row.

**`initiate_subscription(db, *, user: User, tier: SubscriptionTier, provider: BasePaymentProvider) -> tuple[Subscription, Payment, CheckoutResult]`**

1. Create a `Subscription` row: `status=PENDING`, `starts_at=now`, `expires_at=now` (placeholder
   — overwritten on activation; the column is `NOT NULL` so a real value is needed up front).
2. Call `provider.create_payment(CheckoutRequest(amount=tier.price, currency=tier.currency, reference=str(subscription.id), metadata={"subscription_id": ..., "user_id": ..., "tier_id": ...}))`.
3. Create a `Payment` row: `status=PENDING`, `subscription_id=subscription.id`, `user_id=user.id`,
   `provider=provider.provider_name`, `amount=tier.price`, `currency=tier.currency`,
   `provider_transaction_id=<from CheckoutResult>`, `invoice_url=<checkout_url>`.
4. Commit, return `(subscription, payment, checkout_result)`.

**`activate_subscription(db, *, provider_name: PaymentProvider, provider_transaction_id: str, role_client: RoleAssignmentClient) -> Subscription`**

1. Look up `Payment` by `(provider == provider_name, provider_transaction_id)`. Not found →
   raise `PaymentNotFoundError`.
2. **If `payment.status == PaymentStatus.PAID` already** (replay/retry): skip the DB mutation
   entirely (already applied), but still call `role_client.assign_role(...)` again — Discord
   role assignment is idempotent on the Discord side, so this self-heals a prior attempt where
   the DB was updated but the role call failed. Return the existing subscription.
3. Otherwise, load `subscription = payment.subscription`, `tier = subscription.tier`,
   `role_mapping = tier.role_mapping`, `guild = tier.guild`, `user = subscription.user`.
4. Compute the new expiry:
   - If `subscription.status == ACTIVE` and `subscription.expires_at > now` (renewal before
     expiry): extend — `new_expires_at = subscription.expires_at + timedelta(days=tier.duration_days)`.
   - Otherwise (first activation, or resubscribing after `EXPIRED`/`CANCELLED`):
     `subscription.starts_at = now`, `new_expires_at = now + timedelta(days=tier.duration_days)`.
5. Set `payment.status = PAID`, `payment.paid_at = now`; set `subscription.status = ACTIVE`,
   `subscription.expires_at = new_expires_at`. **Commit this before calling the role client** —
   the payment genuinely happened and must be recorded regardless of what happens next.
6. Call `role_client.assign_role(guild_discord_id=guild.guild_id, user_discord_id=user.discord_id, role_discord_id=role_mapping.discord_role_id)`.
7. Write `AuditLog` rows: `PAYMENT_RECEIVED` (step 5), `SUBSCRIPTION_CREATED` or
   `SUBSCRIPTION_EXTENDED` depending on which branch of step 4 ran, and `ROLE_ASSIGNED` (only
   after a successful role call in step 6).
8. Return the subscription.

## Error handling

- Unknown `provider_transaction_id` → `PaymentNotFoundError`. Left for the future webhook route
  to translate into an HTTP response; M8 just defines and raises it.
- Role assignment failure (`role_client.assign_role` raises): propagates to the caller *after*
  the payment/subscription commit in step 5, so the DB correctly reflects "payment received"
  even if Discord is temporarily unreachable. A later retry hits the idempotent branch (step 2)
  and re-attempts only the role call, without re-extending the subscription.
- No new exception hierarchy beyond `PaymentNotFoundError` — role-client errors are whatever the
  concrete `RoleAssignmentClient` implementation raises; the service only needs them to propagate.

## Testing (`backend/tests/test_subscription_service.py`)

Uses the existing in-memory sqlite `db_session` fixture, plus a `FakePaymentProvider`
(`BasePaymentProvider` implementation with scripted responses) and a `FakeRoleClient`
(`RoleAssignmentClient` implementation recording calls). Cases:

1. `initiate_subscription` creates a `PENDING` subscription + payment and returns the fake
   provider's checkout URL/transaction id.
2. `activate_subscription` on a fresh payment → subscription `ACTIVE` with correct
   `expires_at` (`now + duration_days`), payment `PAID`, `assign_role` called once with the
   correct guild/user/role discord ids, and `PAYMENT_RECEIVED` + `SUBSCRIPTION_CREATED` +
   `ROLE_ASSIGNED` audit rows written.
3. Renewal: activate a second payment against an already-`ACTIVE`, non-expired subscription →
   `expires_at` extends from the *previous* `expires_at`, not from `now`; audit action is
   `SUBSCRIPTION_EXTENDED`.
4. Idempotent replay: calling `activate_subscription` twice with the same
   `provider_transaction_id` → subscription/payment state unchanged on the second call (no
   double extension), but `assign_role` is still invoked both times (self-heal check).
5. Unknown transaction id → raises `PaymentNotFoundError`.
6. Role assignment failure (`FakeRoleClient` raises) → payment/subscription are still committed
   as `PAID`/`ACTIVE` even though the exception propagates out of `activate_subscription`.

## Out of scope

- Tier HTTP API (M5) and the concrete `bot_client.py` HTTP implementation of
  `RoleAssignmentClient` (M7) — both referenced only through existing models / the protocol.
- PayPal and NOWPayments concrete `BasePaymentProvider` implementations (M9, M10).
- Checkout and webhook HTTP routes (M9, M10) — `initiate_subscription` /
  `activate_subscription` are the reusable service functions those routes will call.
- Webhook replay-signature hardening beyond the payment-state idempotency in step 2 above
  (M16 — rate limiting, replay-window enforcement, uniform error envelope across all webhooks).
