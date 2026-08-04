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