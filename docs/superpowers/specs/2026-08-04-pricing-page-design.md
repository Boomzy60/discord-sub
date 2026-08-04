# Milestone 6 — Pricing Page (Frontend)

## Context

The pricing page renders live subscription tier data with the pink/purple theme already
established in Milestone 4 (`frontend/src/app/globals.css`), with a "Subscribe" CTA that is
not yet wired to real payments (payments land in M9/M11).

This page depends on the public `GET /tiers` endpoint from Milestone 5
(`docs/superpowers/specs/2026-08-04-subscription-tiers-api-design.md`). That spec was
written and approved in an earlier session but never implemented — only the design doc was
committed. Milestone 5's backend (schemas, service, route, seed script, tests) must be built
first, exactly as already specced, so this page has real data to render. That work is not
re-designed here; it's executed as-is.

## Backend prerequisite (Milestone 5, already specced)

Implemented per the existing M5 spec, unchanged:

- `app/api/deps.py`: `get_active_guild` dependency.
- `app/schemas/subscription_tier.py`: `TierCreate`, `TierUpdate`, `TierOut`.
- `app/services/subscription_tiers.py`: `list_tiers`, `create_tier`, `update_tier`,
  `deactivate_tier`.
- `app/api/routes/tiers.py`: public `GET /tiers`, admin `GET/POST/PATCH/DELETE
  /admin/tiers*`.
- `app/db/seed.py`: seeds 3 placeholder tiers against the bootstrapped guild, so the pricing
  page has real data during local development.
- `backend/tests/test_tiers.py`: mirrors `tests/test_auth.py`'s fixture pattern.

## Frontend data layer

- `frontend/src/lib/types.ts`: add a `Tier` interface mirroring `TierOut`:
  `id, name, description, price, currency, duration_days, active, display_order,
  discord_role_id, created_at`.
- `frontend/src/lib/api.ts`: add `getTiers(): Promise<Tier[]>` — server-side
  `fetch(`${API_BASE_URL}/tiers`, { cache: "no-store" })`, unwraps `ApiEnvelope<Tier[]>`,
  returns `[]` on a non-OK response (matches `getCurrentUser()`'s fail-open pattern in
  `session.ts` — a backend hiccup shows an empty pricing page, not a crashed one).

## Pricing page (`frontend/src/app/pricing/page.tsx`)

Async Server Component (matches the existing `layout.tsx` pattern of awaiting data
server-side). Calls `getTiers()` and `getCurrentUser()` in parallel via `Promise.all`.

- Renders a page heading ("Choose your plan" or similar) and a responsive grid:
  `grid-cols-1 md:grid-cols-3 gap-6`, tiers ordered by `display_order` (already ordered by
  the backend).
- Empty state: if `tiers.length === 0`, render a centered message ("No plans available
  yet — check back soon.") instead of an empty grid. This is the expected state before
  the seed script runs, and must not look broken.

## Tier card (`frontend/src/components/tier-card.tsx`)

Server Component (no client interactivity needed — the CTA is a plain link, not a
client-side handler), props: `tier: Tier`, `isLoggedIn: boolean`, `highlighted: boolean`.

- Built from the existing `Card`/`CardHeader`/`CardTitle`/`CardDescription`/`CardContent`/
  `CardFooter` primitives (`frontend/src/components/ui/card.tsx`) — no new primitives.
- Header: tier name, price formatted as `$X.XX/month` (from `price` + `currency`; MVP is
  monthly-only per `CLAUDE.md`, so no billing-period switch needed).
- Body: `description` split on `\n`, each non-empty line rendered as a bullet with a
  checkmark icon (`lucide-react`, already a shadcn/ui dependency). Admins write one feature
  per line in the description field — no backend schema change.
- Highlight: the page passes `highlighted={true}` to the tier at the middle index only when
  there are exactly 3 tiers (`tiers[1]`). Any other count → no highlight on any card. When
  highlighted: accent-colored ring (`ring-2 ring-accent`), slightly raised
  (`md:-translate-y-2`), and a "Most Popular" `Badge` in the header.
- Footer CTA:
  - Logged out → `<a href={discordLoginUrl()}>Subscribe</a>` (same login link used by
    `LoginButton`; lands on `/dashboard` after auth, matching current OAuth behavior — no
    "return to pricing" redirect, since that would require changing the already-shipped M3
    OAuth flow in `auth.py` and validating against open-redirect risk, which is out of scope
    for this milestone).
  - Logged in → `<Link href={`/checkout?tier=${tier.id}`}>Subscribe</Link>`.

## Checkout stub (`frontend/src/app/checkout/page.tsx`)

Minimal placeholder so the CTA has a real destination instead of a dead link. Reads the
`tier` search param, shows a "Checkout coming soon" message. No payment logic — that's
M9 (PayPal) / M10 (NOWPayments) / M11 (wiring).

## Navbar

No changes needed — `frontend/src/components/navbar.tsx` already links to `/pricing`.

## Testing

- Backend: `test_tiers.py` per the M5 spec's testing section.
- Frontend: no test runner is set up yet in `frontend/` (out of scope to add one for this
  milestone); verification is manual — run the dev server, confirm the pricing page renders
  seeded tiers, empty state, and both CTA states (logged in/out) in the browser.

## Out of scope

- Real payment integration (M9, M10, M11).
- "Return to pricing after login" redirect handling in the OAuth flow.
- Admin tier management UI (M13).
- Automated frontend tests (no test runner configured yet).
