# Milestone 4 — Frontend Skeleton & Login UI (finishing)

## Context

The Next.js app was already scaffolded and Discord OAuth login was wired up on the
frontend side: `Navbar`, `LoginButton`, `UserMenu`, the server-side `getCurrentUser()`
session helper (reads the `session` cookie, calls the backend's `/users/me`), and
`api.ts` (`discordLoginUrl`, `logoutUrl`). The pink/purple theme is already defined in
`globals.css`. shadcn primitives in place: `button`, `card`, `avatar`, `dropdown-menu`,
`badge`, `separator`.

This lines up with the backend auth routes (`backend/app/api/routes/auth.py`):
`GET /auth/discord/login`, `GET /auth/discord/callback` (redirects to
`{frontend_base_url}/dashboard` on success), `POST /auth/logout`, `GET /users/me`. Cookie
name (`session`) and envelope shape (`{success, data, error}`) already match between
frontend and backend.

What's missing: `Navbar` links to `/pricing`, and `UserMenu` links to `/dashboard` and
`/admin` — none of these routes exist, so all three currently 404. The OAuth callback
redirects to `/dashboard` unconditionally, so today a real login lands on a 404. The home
page (`page.tsx`) is still the unmodified `create-next-app` template.

## Scope

Four page additions/changes, no backend changes, no new dependencies:

### 1. `/` (home) — `frontend/src/app/page.tsx`

Replace the boilerplate with a real landing page:
- Hero: headline + one-line description of the service.
- CTA: `LoginButton` if logged out, a "Go to Dashboard" link if logged in. The layout
  already fetches `user` via `getCurrentUser()` for the `Navbar` — pass it down to the
  page as a prop instead of fetching twice.
- A row of 3 static tier-teaser `Card`s (name + one-line blurb only — no price, no data
  fetch). Real tier data doesn't exist until M5/M6.

### 2. `/dashboard` — `frontend/src/app/dashboard/page.tsx`

Server component. Calls `getCurrentUser()`; if `null`, `redirect("/")` (from
`next/navigation`). Renders:
- A welcome card: avatar + display name (reuse the same avatar-URL logic pattern as
  `UserMenu`).
- A placeholder "no active subscription yet" section. Real subscription status is M5+.

This is the one page that must exist for login to work at all, since the OAuth callback
redirects here unconditionally.

### 3. `/pricing` — `frontend/src/app/pricing/page.tsx`

Minimal stub: a single "Pricing tiers — coming soon" card, styled consistently with the
rest of the app. Real content (fetching tiers from the backend) is M6.

### 4. `/admin` — `frontend/src/app/admin/page.tsx`

Server component. Calls `getCurrentUser()`; if `null` or `!user.is_admin`,
`redirect("/")`. Renders an "Admin dashboard — coming soon" placeholder. Real content is
M13.

## Out of scope

- Fetching real subscription tier data (M5 backend, M6 frontend).
- Real dashboard subscription status/management (M12).
- Real admin dashboard functionality (M13).
- Any backend changes — the existing auth routes already provide everything these pages
  need.

## Testing

Frontend has no test runner configured yet — verification is manual: `npm run build`
succeeds, and a manual click-through (login → redirected to `/dashboard` →  navbar shows
`UserMenu` → `/pricing` and `/admin` render without 404 → logout returns to `/`).
