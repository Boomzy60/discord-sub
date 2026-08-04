# Milestone 13 — Admin Dashboard

## Context

Admin auth is already fully wired: `User.is_admin` (`app/models/user.py`), bootstrapped from
`settings.admin_discord_id_set` on first Discord login (`_upsert_user_from_discord_profile` in
`app/api/routes/auth.py`), and enforced via `get_current_admin_user` (`app/api/deps.py`). The
existing `/admin/tiers` CRUD (`app/api/routes/tiers.py`, `app/services/subscription_tiers.py`) is
the pattern to follow: guild-scoped queries, `_: User = Depends(get_current_admin_user)`, flat
Pydantic `*Out` schemas with a `from_x()` classmethod, uniform `{success, data, error}` envelope.

No `app/core/permissions.py` is needed — that responsibility is already covered by
`get_current_admin_user`. M12 (`jobs/expire_subscriptions.py`, automatic expiry) does not exist
yet; this milestone only adds a **manual** revoke path, independent of that job.

`AuditAction.ADMIN_ACTION` exists in `app/models/enums.py` but is currently unused anywhere in
the codebase — this milestone is its first use.

## Components

### `app/services/admin_service.py` (new)

Read-only list queries for the dashboard, each capped at 200 rows, newest first
(`order_by(Model.created_at.desc())`), no pagination:

- `list_users(db) -> list[User]`
- `list_subscriptions(db, *, status: SubscriptionStatus | None = None) -> list[Subscription]` —
  eager-loads `.user` and `.tier` via `selectinload` so the route doesn't N+1.
- `list_payments(db, *, status: PaymentStatus | None = None) -> list[Payment]` — eager-loads
  `.user` via `selectinload`.

### `app/services/subscription_service.py` (addition)

**`revoke_subscription(db: AsyncSession, subscription: Subscription) -> Subscription`**

1. If `subscription.status` is already `CANCELLED` or `EXPIRED`, raise
   `SubscriptionActivationError` — nothing to revoke.
2. Load `tier = await db.get(SubscriptionTier, subscription.tier_id)`, the `TierRoleMapping` for
   that tier, `guild = await db.get(Guild, tier.guild_id)`, `user = await db.get(User,
   subscription.user_id)`. Missing mapping/guild/user → `SubscriptionActivationError` (same
   guard `activate_subscription` already uses).
3. Set `subscription.status = SubscriptionStatus.CANCELLED`, `subscription.cancelled_at = now`,
   `subscription.auto_renew = False`. Commit this before the bot call (mirrors
   `activate_subscription`'s "record the state change first" ordering).
4. Call `await bot_client.remove_role(guild.guild_id, user.discord_id, mapping.discord_role_id)`.
5. Write `AuditLog(user_id=None, action=AuditAction.ADMIN_ACTION, entity_type="subscription",
   entity_id=subscription.id, event_metadata={"reason": "manual_revoke"})` — `user_id` is the
   *acted-upon* user elsewhere in this codebase's audit rows (see `LOGIN`), so it's set to the
   subscription owner's id, not the admin's; the route doesn't currently thread the admin's own
   id any further than the `Depends`, and adding an actor column is out of scope.
6. Return the subscription.

If `bot_client.remove_role` raises, it propagates after the DB commit in step 3 — same
fail-after-persist tradeoff `activate_subscription` already makes, so the subscription is
correctly cancelled in the DB even if Discord is briefly unreachable.

### `app/schemas/admin.py` (new)

Flat DTOs, each with a `from_x(model)` classmethod, matching `TierOut`'s style:

- `AdminUserOut`: `id, discord_id, username, global_name, avatar, email, is_admin, last_login, created_at`
- `AdminSubscriptionOut`: `id, user_id, username, tier_id, tier_name, status, starts_at,
  expires_at, cancelled_at, auto_renew, created_at`
- `AdminPaymentOut`: `id, user_id, username, subscription_id, provider, payment_method, amount,
  currency, status, provider_transaction_id, paid_at, created_at`

### `app/api/routes/admin.py` (new)

All routes behind `_: User = Depends(get_current_admin_user)`:

- `GET /admin/users` → `list[AdminUserOut]`
- `GET /admin/subscriptions?status=` (optional `SubscriptionStatus` query param) → `list[AdminSubscriptionOut]`
- `GET /admin/payments?status=` (optional `PaymentStatus` query param) → `list[AdminPaymentOut]`
- `POST /admin/subscriptions/{id}/revoke` → calls `subscription_service.revoke_subscription`,
  returns the updated `AdminSubscriptionOut`. 404 if the id doesn't exist;
  `SubscriptionActivationError` → 409 (mirrors how other services' domain errors already map to
  4xx in this codebase's exception handling); `bot_client.BotClientError` is caught explicitly in
  the route and re-raised as `HTTPException(502)` (the DB state is already committed by that
  point, so this only tells the admin Discord needs a manual follow-up — it does not roll back).

Registered in `app/main.py` next to the other routers.

## Frontend

### `app/admin/page.tsx` (new, server component)

`getCurrentUser()` → redirect to `/` if `null` or `!user.is_admin` (same guard shape used
elsewhere). Fetches all three lists server-side (`cache: "no-store"`, same as `getTiers`), passes
them into a client-side tabbed view.

### `components/admin/admin-tabs.tsx` (new, `"use client"`)

shadcn `Tabs` (Users / Subscriptions / Payments), pink/purple theme already defined in
`globals.css` — no new UI primitives needed.

### `components/admin/users-table.tsx`, `subscriptions-table.tsx`, `payments-table.tsx` (new)

Plain `<table>` styled with existing `Card`/`Badge` components. `subscriptions-table.tsx` is
`"use client"` and owns the revoke action: a "Revoke" button per `ACTIVE` row, native `confirm()`
guard (destructive, no undo), calls `revokeSubscription(id)`, then `router.refresh()` on success;
shows the API's error string on failure.

### `lib/api.ts` (additions)

`getAdminUsers()`, `getAdminSubscriptions()`, `getAdminPayments()` (mirror `getTiers`'s
fetch-and-unwrap-envelope shape), `revokeSubscription(id)` (mirrors `startCheckout`'s
POST-with-credentials-and-throw-on-error shape).

### `lib/types.ts` (additions)

`AdminUser`, `AdminSubscription`, `AdminPayment` interfaces matching the backend DTOs.

## Error handling

- Non-admin hitting any `/admin/*` route → 403 (existing `get_current_admin_user` behavior,
  unchanged).
- Revoking an already-cancelled/expired subscription → 409, surfaced as the button's error state
  on the frontend (button disabled for non-`ACTIVE` rows in the first place, so this is a
  defense-in-depth path, e.g. concurrent double-click).
- Revoking a subscription with no role mapping/guild/user → 409, same as above; this path exists
  in `activate_subscription` today and unassigned/misconfigured tiers can reach it.
- `bot_client.remove_role` unreachable → the subscription is still cancelled in the DB (see
  service section); the route returns 502 in that case so the admin knows the Discord side needs
  a manual follow-up, while the frontend still shows the row as cancelled on refresh.

## Testing

`backend/tests/test_admin.py`:
- Each `GET /admin/*` route: 401 unauthenticated, 403 non-admin, 200 + correct shape for admin.
- `POST /admin/subscriptions/{id}/revoke`: happy path (status flips to `CANCELLED`,
  `bot_client.remove_role` called once, audit row written), 404 unknown id, 409 already-cancelled.

`backend/tests/test_subscription_service.py` (addition): unit tests for `revoke_subscription`
directly — happy path, already-terminal-status guard, missing-mapping guard — following the
existing `FakeRoleClient`/fixture patterns already in that file.

No frontend automated tests exist yet in this repo (no test runner configured for
`frontend/`), so `app/admin/page.tsx` and its components are verified manually in-browser per
this project's usual workflow, not with new test files.

## Out of scope

- M12's automatic expiry job — this milestone's revoke is admin-triggered only.
- Pagination — capped at 200 rows per list, per current test-server scale; revisit if/when this
  becomes a real constraint.
- An `admin_id`/actor column on `AuditLog` for who performed the revoke — the table only has
  `user_id` (the subject), and adding an actor column is a schema change beyond this milestone's
  scope.
- Surfacing `/admin/tiers` CRUD in the new dashboard UI — it stays API-only for now (per design
  discussion with the user).
