# Milestone 5 — Subscription Tiers (Data + API)

## Context

The `SubscriptionTier` and `TierRoleMapping` models (and their Alembic migration) already
exist from the earlier "database models" milestone. This milestone adds the API layer on
top of them: admin management of tiers, and a public endpoint for the pricing page.

There is exactly one Discord guild managed by the platform at a time (the "test server
first, migrate to production later" workflow described in `CLAUDE.md`). No Guild CRUD API
exists yet, so tier requests need a way to resolve the single `guilds.id` row they belong to.

## Guild resolution

A new `get_active_guild` dependency in `app/api/deps.py`:

- Looks up `Guild` where `guild_id == settings.discord_guild_id`.
- If no row exists, creates one (`guild_name="Discord Server"`, `active=True`) and commits.
- Returns the `Guild` row for use by tier routes.

This means no manual setup step is needed before tiers can be created, and migrating to the
client's production server later is just changing `DISCORD_GUILD_ID` in the environment —
no code change.

## Schemas (`app/schemas/subscription_tier.py`)

- `TierCreate`: `name: str`, `description: str | None`, `price: float` (>0),
  `currency: str = "USD"`, `duration_days: int` (>0), `discord_role_id: str` (non-empty).
  `billing_period` is not client-settable — the service hardcodes `BillingPeriod.MONTHLY`,
  so no invalid value can ever reach the database. This matches the MVP's monthly-only
  requirement while leaving the enum's other values available for a future change.
- `TierUpdate`: all `TierCreate` fields optional (PATCH semantics), plus
  `active: bool | None` and `display_order: int | None`.
- `TierOut`: mirrors `SubscriptionTier` columns, plus a flattened `discord_role_id` read
  from the related `TierRoleMapping`. Built with `from_attributes = True`.

## Service layer (`app/services/subscription_tiers.py`)

Business logic lives here, not in routes, per project conventions.

- `list_tiers(db, guild_id, *, only_active: bool) -> list[SubscriptionTier]`
  Ordered by `display_order`. `only_active=True` filters to `active == True`.
- `create_tier(db, guild_id, data: TierCreate) -> SubscriptionTier`
  Creates the `SubscriptionTier` (with `billing_period=MONTHLY`) and its
  `TierRoleMapping` in the same transaction.
- `update_tier(db, guild_id, tier_id, data: TierUpdate) -> SubscriptionTier`
  Raises 404 if the tier doesn't exist or belongs to a different guild. Updates only the
  fields present in the payload. If `discord_role_id` is present, updates the existing
  `TierRoleMapping` row.
- `deactivate_tier(db, guild_id, tier_id) -> None`
  Sets `active = False`. This is what "delete" means in the admin API — a hard delete would
  risk orphaning historical `Subscription` rows that FK to the tier, so tiers are retired,
  not removed. Raises 404 under the same conditions as `update_tier`.

## Routes (`app/api/routes/tiers.py`)

| Method | Path                    | Auth        | Behavior                                   |
|--------|-------------------------|-------------|---------------------------------------------|
| GET    | `/tiers`                | public      | Active tiers only, for the pricing page.     |
| GET    | `/admin/tiers`          | admin       | All tiers (active + inactive) for the guild. |
| POST   | `/admin/tiers`          | admin       | Create a tier + its role mapping.            |
| PATCH  | `/admin/tiers/{tier_id}`| admin       | Update tier fields / role mapping.           |
| DELETE | `/admin/tiers/{tier_id}`| admin       | Deactivate (see above).                      |

All responses use the existing `{"success", "data", "error"}` envelope (see
`app/core/errors.py` and `app/api/routes/auth.py`). Admin routes depend on the existing
`get_current_admin_user`; all tier routes depend on the new `get_active_guild`.

Router is registered in `app/main.py` alongside `health` and `auth`.

## Testing

`backend/tests/test_tiers.py`, following the `test_auth.py` pattern (in-memory sqlite via
the existing `client` / `db_session` fixtures):

- Public `GET /tiers` returns only active tiers, ordered by `display_order`.
- Admin `GET /admin/tiers` returns active + inactive tiers.
- Admin create/update/deactivate happy paths, including that update/deactivate correctly
  touch the `TierRoleMapping` row.
- Non-admin (or unauthenticated) requests to `/admin/tiers*` are rejected (401/403).
- Update/deactivate on a nonexistent or cross-guild tier ID returns 404.

## Out of scope

- Guild CRUD API (guild is bootstrapped implicitly, per above).
- Subscription purchase flow, payments, and role assignment — later milestones.
- Enforcing "exactly three tiers" as a hard API constraint — that's a content decision for
  whoever operates the admin dashboard, not a structural limit worth baking into the API.
