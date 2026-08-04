# Local Development

## Prerequisites

- Docker and Docker Compose
- A Supabase Postgres project (session pooler connection string)
- A test Discord application + bot token, invited to a test server

## First-time setup

1. Copy the env template and fill in real values (never commit `.env`):

   ```
   cp .env.example .env
   ```

2. Build and start the stack:

   ```
   docker compose up --build
   ```

   This starts three services on a shared Docker network:

   | Service  | Container port | Host URL                | Purpose                          |
   |----------|-----------------|--------------------------|-----------------------------------|
   | backend  | 8000            | http://localhost:8000    | FastAPI app                       |
   | bot      | 8001            | http://localhost:8001    | discord.py bot + internal role API|
   | frontend | 3000            | http://localhost:3000    | Next.js app                       |

   `backend` waits for `bot` to report healthy, and `frontend` waits for `backend`, so the
   first boot may take a few seconds longer than subsequent ones.

3. Run database migrations (once the backend container is up):

   ```
   docker compose exec backend alembic upgrade head
   ```

## Everyday workflow

- Source code for all three services is bind-mounted into the containers, so edits on the
  host are picked up without rebuilding:
  - `backend` and `bot` run with `uvicorn --reload` / a plain Python process — restart the
    relevant service (`docker compose restart bot`) after editing bot code, since discord.py
    doesn't hot-reload.
  - `frontend` runs `next dev`, which hot-reloads automatically.
- `frontend/node_modules` and `frontend/.next` are excluded from the bind mount (via
  anonymous volumes in `docker-compose.yml`) so the Linux container uses its own installed
  dependencies instead of your host's, which may contain platform-specific native binaries.
- Only rebuild an image when its dependency files change:

  ```
  docker compose build backend   # after editing backend/requirements*.txt
  docker compose build bot       # after editing bot/requirements*.txt
  docker compose build frontend  # after editing frontend/package.json
  ```

## Running tests

```
docker compose exec backend pytest
docker compose exec bot pytest
```

## Health checks

Each service exposes a health endpoint that Docker polls automatically:

- backend: `GET /health`
- bot: `GET /internal/health`
- frontend: `GET /`

Check status with `docker compose ps`.

## Stopping

```
docker compose down
```

Add `-v` to also remove the frontend's anonymous `node_modules`/`.next` volumes if you need
a completely clean reinstall.

## Troubleshooting

- **Frontend container fails to start with native-module errors**: this usually means the
  anonymous volumes for `node_modules`/`.next` were removed or shadowed. Run
  `docker compose down -v && docker compose up --build frontend` to reinstall cleanly.
- **Backend can't reach the bot's internal API**: the backend container calls the bot at
  `http://bot:8001` (the Compose service name), not `localhost`. This is set via the
  `BOT_INTERNAL_API_URL` override in `docker-compose.yml` and only applies inside the
  Docker network — local (non-Docker) runs should keep using `http://localhost:8001` in `.env`.
