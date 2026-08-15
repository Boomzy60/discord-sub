# Kiyomi Studios

Production subscription platform for Discord communities: Discord OAuth login, three monthly
subscription tiers, PayPal and NOWPayments (crypto) payment, automatic role grant/revoke tied to
subscription status.

See [CLAUDE.md](CLAUDE.md) for the full project specification.

## Architecture

```
Frontend (Next.js) -> FastAPI Backend -> Supabase (Postgres) -> Discord Bot -> Discord Server
```

- The frontend never talks to the database directly; all business logic lives in the backend.
- The bot only performs Discord operations (role assign/remove); subscription and payment
  decisions are made by the backend and sent to the bot.

## Services

| Service    | Path         | Stack                              |
|------------|--------------|-------------------------------------|
| Frontend   | `frontend/`  | Next.js, TypeScript, Tailwind, shadcn/ui |
| Backend    | `backend/`   | FastAPI, SQLAlchemy, Alembic, Pydantic |
| Bot        | `bot/`       | discord.py |

## Local Development

1. Copy `.env.example` to `.env` and fill in real values (Discord app credentials, Supabase
   connection string, PayPal/NOWPayments sandbox keys).
2. `docker-compose up --build`

Each service's own setup notes will be added as it's implemented.
