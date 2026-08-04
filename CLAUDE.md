# CLAUDE.md

# Discord Subscription Platform

## Objective

Build a production-ready subscription platform for Discord communities.

Users should be able to:

1. Visit a website.
2. Log in with Discord OAuth.
3. Purchase one of three subscription tiers.
4. Automatically receive the corresponding Discord role after successful payment.
5. Automatically lose the role when the subscription expires.

The experience should require no manual intervention from the server owner.

---

# Client Requirements

The agreed MVP includes:

- Discord OAuth login
- Website
- FastAPI backend
- Discord bot
- Three subscription tiers
- Monthly subscriptions only
- PayPal payments
- One cryptocurrency payment provider (NOWPayments)
- Automatic Discord role assignment
- Automatic role removal on expiry
- Basic admin dashboard
- Test Discord server first
- Easy migration to the client's production Discord server
- Pink and purple UI
- Simple, clean interface
- No reseller or redeem-code system
- Future support for Alipay and WeChat Pay without major architectural changes

---

# Tech Stack

Frontend

- Next.js
- TypeScript
- TailwindCSS
- shadcn/ui

Backend

- FastAPI
- SQLAlchemy
- Alembic
- Pydantic

Database

- PostgreSQL (Supabase) (im using a session pooler connection)

Bot

- discord.py

Payments

- PayPal
- NOWPayments

Deployment

- Docker
- Docker Compose
- Cloudzy VPS
- Cloudflare
- Caddy

---

# Architecture

Frontend

↓

FastAPI Backend

↓

Supabase

↓

Discord Bot

↓

Discord Server

The frontend must never communicate directly with the database.

All business logic belongs in the backend.

The Discord bot should only manage Discord operations. Business decisions (subscriptions, payments, expirations) belong to the backend.

---

# Engineering Principles

- Build incrementally.
- Keep modules small and maintainable.
- Follow SOLID principles where practical.
- Use dependency injection.
- Prefer composition over inheritance.
- Use asynchronous code where appropriate.
- Keep business logic separate from API routes.
- Write production-quality code.
- Avoid duplication.

---

# Security

- Never hardcode secrets.
- Use environment variables.
- Validate every request.
- Verify all payment webhooks.
- Never trust the frontend.
- Never activate subscriptions before payment confirmation.
- Use UUID primary keys.
- Store Discord IDs as strings.
- Use UTC timestamps.

---

# Code Quality

- Use strict typing.
- Keep functions focused.
- Use descriptive names.
- Write docstrings for public classes and functions.
- Add logging where useful.
- Return consistent API responses.
- Handle errors gracefully.

---

# Workflow

Implement the project one milestone at a time.

Before starting each milestone:

1. Inspect the current repository.
2. Reuse existing code.
3. Avoid unnecessary rewrites.
4. Only modify files relevant to the current task.

After completing a milestone:

- Ensure the project builds.
- Ensure existing functionality still works.
- Summarize what was implemented.
- Suggest the next milestone.

---

# Definition of Done

A feature is complete only if:

- It works.
- It is typed.
- It is tested where appropriate.
- It follows the existing architecture.
- It integrates cleanly with the rest of the project.

Never sacrifice maintainability for speed.

When uncertain, choose the solution that is easier to extend in future.

Milestone 0 — Project Scaffolding & Environment Config
Objective: Establish repo structure, env var pattern, docker-compose skeleton, git init.
Files: .gitignore, .env.example, README.md, docker-compose.yml (service stubs), backend/Dockerfile, bot/Dockerfile, frontend/Dockerfile (placeholders)
Dependencies: None
Deliverable: docker-compose config validates; git initialized with first commit; documented env vars (no secrets committed).

Milestone 1 — Backend Skeleton & Configuration
Objective: FastAPI app with pydantic-settings config, structured logging, health endpoint, pytest baseline.
Files: backend/app/main.py, backend/app/core/config.py, backend/app/core/logging.py, backend/app/api/routes/health.py, backend/pyproject.toml, backend/tests/test_health.py
Dependencies: M0
Deliverable: GET /health returns 200; backend container builds/runs via compose; tests pass.

Milestone 2 — Database Layer & Migrations
Objective: Async SQLAlchemy engine (Supabase session pooler), Alembic setup, base models (User, Tier, Subscription, Payment) with UUID PKs, string Discord IDs, UTC timestamps.
Files: backend/app/db/session.py, backend/app/models/*.py, backend/alembic/, migration files
Dependencies: M1
Deliverable: alembic upgrade head creates tables in Supabase; model tests confirm UUID/timestamp defaults.

Milestone 3 — Discord OAuth Login (Backend)
Objective: OAuth2 authorization-code flow: login redirect, callback, token exchange, user upsert, JWT session cookie.
Files: backend/app/api/routes/auth.py, backend/app/services/discord_oauth.py, backend/app/core/security.py, backend/tests/test_auth.py
Dependencies: M2
Deliverable: /auth/discord/login → Discord → callback creates/updates user, sets session; /users/me returns current user (tested with mocked Discord API).

Milestone 4 — Frontend Skeleton & Login UI
Objective: Next.js + TS + Tailwind + shadcn/ui scaffold, pink/purple theme, "Login with Discord" button, session-aware layout.
Files: frontend/app/layout.tsx, frontend/app/page.tsx, frontend/tailwind.config.ts, frontend/lib/api.ts, frontend/app/dashboard/page.tsx
Dependencies: M3, M0
Deliverable: User logs in against test Discord server end-to-end, lands on dashboard showing their username/avatar.

Milestone 5 — Subscription Tiers (Data + API)
Objective: Tier model/seed (3 tiers: name, price, discord_role_id, monthly billing), admin CRUD, public GET /tiers.
Files: backend/app/models/tier.py, backend/app/api/routes/tiers.py, backend/app/services/tier_service.py, backend/app/db/seed.py, tests
Dependencies: M2, M3 (admin auth)
Deliverable: GET /tiers returns seeded tiers; admin endpoints protected and tested.

Milestone 6 — Pricing Page (Frontend)
Objective: Render live tier data with pink/purple cards; "Subscribe" CTA (not yet wired to payment).
Files: frontend/app/pricing/page.tsx, frontend/components/tier-card.tsx
Dependencies: M4, M5
Deliverable: Pricing page displays real backend tier data in browser.

Milestone 7 — Discord Bot Skeleton & Internal Role API
Objective: discord.py bot connected to test server; internal authenticated API (assign_role/remove_role) secured by shared secret; backend client to call it.
Files: bot/main.py, bot/app/internal_api.py, bot/app/discord_client.py, backend/app/services/bot_client.py
Dependencies: M1, M0
Deliverable: Backend call → bot assigns/removes a real role on the test Discord server.

Milestone 8 — Payment Provider Abstraction Layer
Objective: Provider-agnostic interface (create_payment, verify_webhook, parse_webhook_event) + subscription activation service — so PayPal, NOWPayments, and future Alipay/WeChat plug in without rearchitecting.
Files: backend/app/services/payments/base.py, backend/app/services/subscription_service.py, backend/tests/test_subscription_service.py (fake provider)
Dependencies: M2, M5
Deliverable: Unit tests prove full activation flow (payment confirmed → role assignment call) against a fake in-memory provider.

Milestone 9 — PayPal Integration
Objective: PayPalProvider, checkout endpoint, verified webhook activating subscriptions via M8's service.
Files: backend/app/services/payments/paypal.py, backend/app/api/routes/payments_paypal.py, backend/app/api/routes/webhooks_paypal.py, tests
Dependencies: M8
Deliverable: Sandbox PayPal checkout → verified webhook → subscription active → role assigned on test server.

Milestone 10 — NOWPayments Integration
Objective: NOWPaymentsProvider, HMAC-verified IPN webhook, crypto checkout endpoint.
Files: backend/app/services/payments/nowpayments.py, backend/app/api/routes/payments_crypto.py, backend/app/api/routes/webhooks_nowpayments.py, tests
Dependencies: M8
Deliverable: Sandbox crypto invoice → verified IPN → subscription active, identical outcome to PayPal path.

Milestone 11 — Checkout Frontend Flow
Objective: Wire pricing page to both payment methods; payment-method selector; success/cancel pages.
Files: frontend/app/checkout/page.tsx, frontend/components/payment-method-selector.tsx
Dependencies: M6, M9, M10
Deliverable: Full manual flow: login → choose tier → pay (PayPal sandbox) → role appears on test Discord server.

Milestone 12 — Expiration & Automatic Role Removal
Objective: Scheduled job (APScheduler) finding expired subscriptions, marking expired, revoking role via bot.
Files: backend/app/jobs/expire_subscriptions.py, backend/app/core/scheduler.py, tests
Dependencies: M7, M9/M10
Deliverable: Artificially-expired subscription row → job removes Discord role and updates DB status.

Milestone 13 — Admin Dashboard
Objective: Admin endpoints (list users/subscriptions/payments, manual revoke), gated frontend admin pages.
Files: backend/app/api/routes/admin.py, backend/app/core/permissions.py, frontend/app/admin/*
Dependencies: M3, M5, M9/M10, M12
Deliverable: Admin views all subscribers/status; manual revoke works end-to-end.

Milestone 14 — Dockerized Full Stack
Objective: Finalize docker-compose.yml wiring backend/frontend/bot with healthchecks/networking; document local dev workflow.
Files: docker-compose.yml, .env.example, docs/DEV.md
Dependencies: All prior
Deliverable: docker-compose up boots entire stack against Supabase + test Discord server; smoke test passes.

Milestone 15 — Production Deployment
Objective: Caddy reverse proxy + TLS, Cloudflare DNS, prod compose override, migration runbook to client's production Discord server.
Files: Caddyfile, docker-compose.prod.yml, docs/DEPLOYMENT.md, docs/MIGRATION_TO_PROD_DISCORD.md
Dependencies: M14
Deliverable: Staging deployment live via HTTPS on Cloudzy VPS; documented no-code-change migration path to client's real server.

Milestone 16 — Hardening Pass
Objective: Consistent API error envelope, webhook replay protection, rate limiting, expanded test coverage, security review.
Files: backend/app/core/errors.py, middleware, cross-cutting tests
Dependencies: All functional milestones
Deliverable: All webhook endpoints reject invalid/replayed signatures with tests; uniform response envelope across API.


NB: DONT TREAT AS SMTH COMPLEX. ITS REALLY SIMPLE. DONT OVERCOMPLICATE.