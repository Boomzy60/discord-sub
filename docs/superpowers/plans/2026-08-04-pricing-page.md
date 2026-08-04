# Milestone 5 (Tiers API) + Milestone 6 (Pricing Page) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the subscription tiers API (backend) exactly as already specced in `docs/superpowers/specs/2026-08-04-subscription-tiers-api-design.md`, then build a pricing page (frontend) that renders live tier data with a Subscribe CTA, per `docs/superpowers/specs/2026-08-04-pricing-page-design.md`.

**Architecture:** Backend: Pydantic schemas → service layer (business logic, DB access) → FastAPI routes, following the existing `auth.py`/`discord_oauth.py` layering. A single `Guild` row is bootstrapped lazily from `settings.discord_guild_id` the first time it's needed. Frontend: an async Server Component page fetches tiers + current user server-side and renders them through a presentational `TierCard` component built from existing shadcn/ui primitives.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, pytest + pytest-asyncio + aiosqlite (backend, all already installed — no new dependencies). Next.js 16 App Router, TypeScript, existing shadcn/ui `Card`/`Badge`/`Button` primitives, `lucide-react` (frontend, all already installed — no new dependencies).

## Global Constraints

- API responses use the existing envelope: `{"success": bool, "data": ..., "error": ...}` (see `app/core/errors.py`, `app/api/routes/auth.py`).
- Business logic lives in the service layer, not in routes (`CLAUDE.md` engineering principles).
- UUID primary keys, Discord IDs as strings, UTC timestamps — already enforced by `UUIDPrimaryKeyMixin`/`TimestampMixin` in `app/db/base.py`; don't deviate.
- MVP is monthly-billing only: `billing_period` is never client-settable — the service always sets `BillingPeriod.MONTHLY`.
- No new backend or frontend dependencies — everything needed is already in `requirements.txt`, `requirements-dev.txt`, and `frontend/package.json`.
- No frontend test runner is configured; frontend tasks are verified with `npm run build` (type-check + lint) plus manual browser checks, not automated tests.
- Follow existing patterns exactly: `tests/conftest.py`'s `client`/`db_session` fixtures for backend tests, `LayoutProps<'/...'>`/`PageProps<'/...'>` typed route helpers for frontend pages (per `frontend/node_modules/next/dist/docs/01-app/01-getting-started/03-layouts-and-pages.md` — this Next.js 16 install differs from older training data, see `frontend/AGENTS.md`).

---

### Task 1: Tier schemas (`TierCreate`, `TierUpdate`, `TierOut`)

**Files:**
- Create: `backend/app/schemas/subscription_tier.py`
- Test: `backend/tests/test_tier_schemas.py`

**Interfaces:**
- Consumes: `app.models.subscription_tier.SubscriptionTier`, `app.models.tier_role_mapping.TierRoleMapping` (existing models).
- Produces: `TierCreate(name, description, price, currency, duration_days, discord_role_id)`, `TierUpdate(name?, description?, price?, currency?, duration_days?, discord_role_id?, active?, display_order?)`, `TierOut(id, name, description, price, currency, duration_days, active, display_order, discord_role_id, created_at)` with classmethod `TierOut.from_tier(tier: SubscriptionTier) -> TierOut`. Later tasks (service, routes) import these three names from `app.schemas.subscription_tier`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_tier_schemas.py
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.subscription_tier import SubscriptionTier
from app.models.tier_role_mapping import TierRoleMapping
from app.schemas.subscription_tier import TierCreate, TierOut


def test_tier_create_rejects_non_positive_price():
    with pytest.raises(ValidationError):
        TierCreate(name="Bronze", price=0, duration_days=30, discord_role_id="123456789012345678")


def test_tier_create_applies_defaults():
    tier = TierCreate(name="Bronze", price=4.99, duration_days=30, discord_role_id="123456789012345678")

    assert tier.currency == "USD"
    assert tier.description is None


def test_tier_out_from_tier_flattens_role_mapping():
    tier = SubscriptionTier(
        id=uuid.uuid4(),
        guild_id=uuid.uuid4(),
        name="Bronze",
        description="Perk one\nPerk two",
        price=4.99,
        currency="USD",
        duration_days=30,
        active=True,
        display_order=0,
        created_at=datetime.now(timezone.utc),
    )
    tier.role_mapping = TierRoleMapping(discord_role_id="123456789012345678")

    out = TierOut.from_tier(tier)

    assert out.discord_role_id == "123456789012345678"
    assert out.price == 4.99
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_tier_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.subscription_tier'`

- [ ] **Step 3: Write the schemas**

```python
# backend/app/schemas/subscription_tier.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.subscription_tier import SubscriptionTier


class TierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = None
    price: float = Field(gt=0)
    currency: str = "USD"
    duration_days: int = Field(gt=0)
    discord_role_id: str = Field(min_length=1)


class TierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    currency: str | None = None
    duration_days: int | None = Field(default=None, gt=0)
    discord_role_id: str | None = Field(default=None, min_length=1)
    active: bool | None = None
    display_order: int | None = None


class TierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    price: float
    currency: str
    duration_days: int
    active: bool
    display_order: int
    discord_role_id: str
    created_at: datetime

    @classmethod
    def from_tier(cls, tier: SubscriptionTier) -> "TierOut":
        return cls(
            id=tier.id,
            name=tier.name,
            description=tier.description,
            price=float(tier.price),
            currency=tier.currency,
            duration_days=tier.duration_days,
            active=tier.active,
            display_order=tier.display_order,
            discord_role_id=tier.role_mapping.discord_role_id,
            created_at=tier.created_at,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_tier_schemas.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/subscription_tier.py backend/tests/test_tier_schemas.py
git commit -m "feat(backend): add subscription tier schemas"
```

---

### Task 2: `get_active_guild` dependency

**Files:**
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/test_deps.py`

**Interfaces:**
- Consumes: `app.models.Guild`, `app.core.config.get_settings` (existing), `app.db.session.get_db` (existing).
- Produces: `async def get_active_guild(db: AsyncSession = Depends(get_db)) -> Guild`. Later tasks (routes, seed script) import and call this directly.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_deps.py
from sqlalchemy import select

from app.api.deps import get_active_guild
from app.core.config import get_settings
from app.models import Guild


async def test_get_active_guild_creates_guild_when_missing(db_session):
    guild = await get_active_guild(db=db_session)

    assert guild.guild_id == get_settings().discord_guild_id
    assert guild.active is True

    result = await db_session.execute(select(Guild))
    assert len(result.scalars().all()) == 1


async def test_get_active_guild_returns_existing_guild(db_session):
    first = await get_active_guild(db=db_session)
    second = await get_active_guild(db=db_session)

    assert first.id == second.id

    result = await db_session.execute(select(Guild))
    assert len(result.scalars().all()) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_deps.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_active_guild' from 'app.api.deps'`

- [ ] **Step 3: Add the dependency**

Modify `backend/app/api/deps.py` — add these imports at the top alongside the existing ones:

```python
from app.core.config import get_settings
from app.models import Guild, User
```

(Replace the existing `from app.models import User` import with the combined line above.) Then append at the end of the file:

```python
async def get_active_guild(db: AsyncSession = Depends(get_db)) -> Guild:
    settings = get_settings()
    result = await db.execute(select(Guild).where(Guild.guild_id == settings.discord_guild_id))
    guild = result.scalar_one_or_none()
    if guild is None:
        guild = Guild(guild_id=settings.discord_guild_id, guild_name="Discord Server", active=True)
        db.add(guild)
        await db.commit()
        await db.refresh(guild)
    return guild
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_deps.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full backend test suite to confirm nothing else broke**

Run: `cd backend && python -m pytest -v`
Expected: PASS (all tests, including pre-existing ones)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/deps.py backend/tests/test_deps.py
git commit -m "feat(backend): add get_active_guild dependency"
```

---

### Task 3: Tier service layer

**Files:**
- Create: `backend/app/services/subscription_tiers.py`
- Test: `backend/tests/test_subscription_tiers_service.py`

**Interfaces:**
- Consumes: `TierCreate`, `TierUpdate` from Task 1 (`app.schemas.subscription_tier`); `SubscriptionTier`, `TierRoleMapping`, `BillingPeriod` (existing models/enums).
- Produces: `async def list_tiers(db, guild_id: uuid.UUID, *, only_active: bool) -> list[SubscriptionTier]`, `async def create_tier(db, guild_id: uuid.UUID, data: TierCreate) -> SubscriptionTier`, `async def update_tier(db, guild_id: uuid.UUID, tier_id: uuid.UUID, data: TierUpdate) -> SubscriptionTier` (raises `HTTPException(404)` if not found), `async def deactivate_tier(db, guild_id: uuid.UUID, tier_id: uuid.UUID) -> None` (raises `HTTPException(404)` if not found). All returned `SubscriptionTier` objects have `.role_mapping` eagerly loaded. Later tasks (routes, seed script) import all four functions from `app.services.subscription_tiers`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_subscription_tiers_service.py
import pytest
from fastapi import HTTPException

from app.models import Guild
from app.schemas.subscription_tier import TierCreate, TierUpdate
from app.services import subscription_tiers as tier_service


async def _make_guild(db_session) -> Guild:
    guild = Guild(guild_id="test-guild", guild_name="Test Guild", active=True)
    db_session.add(guild)
    await db_session.commit()
    await db_session.refresh(guild)
    return guild


async def test_create_tier_creates_tier_and_role_mapping(db_session):
    guild = await _make_guild(db_session)

    tier = await tier_service.create_tier(
        db_session, guild.id, TierCreate(name="Bronze", price=4.99, duration_days=30, discord_role_id="111")
    )

    assert tier.name == "Bronze"
    assert tier.role_mapping.discord_role_id == "111"
    assert tier.billing_period.value == "MONTHLY"


async def test_list_tiers_orders_by_display_order_and_filters_active(db_session):
    guild = await _make_guild(db_session)
    tier_a = await tier_service.create_tier(
        db_session, guild.id, TierCreate(name="A", price=1, duration_days=30, discord_role_id="1")
    )
    tier_b = await tier_service.create_tier(
        db_session, guild.id, TierCreate(name="B", price=2, duration_days=30, discord_role_id="2")
    )
    tier_a.display_order = 1
    tier_b.display_order = 0
    await db_session.commit()
    await tier_service.deactivate_tier(db_session, guild.id, tier_a.id)

    active_only = await tier_service.list_tiers(db_session, guild.id, only_active=True)
    all_tiers = await tier_service.list_tiers(db_session, guild.id, only_active=False)

    assert [t.name for t in active_only] == ["B"]
    assert [t.name for t in all_tiers] == ["B", "A"]


async def test_update_tier_updates_fields_and_role_mapping(db_session):
    guild = await _make_guild(db_session)
    tier = await tier_service.create_tier(
        db_session, guild.id, TierCreate(name="Bronze", price=4.99, duration_days=30, discord_role_id="111")
    )

    updated = await tier_service.update_tier(
        db_session, guild.id, tier.id, TierUpdate(price=9.99, discord_role_id="222")
    )

    assert float(updated.price) == 9.99
    assert updated.role_mapping.discord_role_id == "222"
    assert updated.name == "Bronze"


async def test_update_tier_raises_404_for_unknown_tier(db_session):
    guild = await _make_guild(db_session)

    with pytest.raises(HTTPException) as exc_info:
        await tier_service.update_tier(db_session, guild.id, guild.id, TierUpdate(price=1))

    assert exc_info.value.status_code == 404


async def test_deactivate_tier_sets_active_false(db_session):
    guild = await _make_guild(db_session)
    tier = await tier_service.create_tier(
        db_session, guild.id, TierCreate(name="Bronze", price=4.99, duration_days=30, discord_role_id="111")
    )

    await tier_service.deactivate_tier(db_session, guild.id, tier.id)
    await db_session.refresh(tier)

    assert tier.active is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_subscription_tiers_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.subscription_tiers'`

- [ ] **Step 3: Write the service**

```python
# backend/app/services/subscription_tiers.py
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import BillingPeriod
from app.models.subscription_tier import SubscriptionTier
from app.models.tier_role_mapping import TierRoleMapping
from app.schemas.subscription_tier import TierCreate, TierUpdate


async def _get_owned_tier(db: AsyncSession, guild_id: uuid.UUID, tier_id: uuid.UUID) -> SubscriptionTier:
    result = await db.execute(
        select(SubscriptionTier)
        .options(selectinload(SubscriptionTier.role_mapping))
        .where(SubscriptionTier.id == tier_id, SubscriptionTier.guild_id == guild_id)
    )
    tier = result.scalar_one_or_none()
    if tier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tier not found")
    return tier


async def list_tiers(db: AsyncSession, guild_id: uuid.UUID, *, only_active: bool) -> list[SubscriptionTier]:
    stmt = (
        select(SubscriptionTier)
        .options(selectinload(SubscriptionTier.role_mapping))
        .where(SubscriptionTier.guild_id == guild_id)
        .order_by(SubscriptionTier.display_order)
    )
    if only_active:
        stmt = stmt.where(SubscriptionTier.active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_tier(db: AsyncSession, guild_id: uuid.UUID, data: TierCreate) -> SubscriptionTier:
    tier = SubscriptionTier(
        guild_id=guild_id,
        name=data.name,
        description=data.description,
        price=data.price,
        currency=data.currency,
        billing_period=BillingPeriod.MONTHLY,
        duration_days=data.duration_days,
    )
    db.add(tier)
    await db.flush()

    db.add(TierRoleMapping(guild_id=guild_id, tier_id=tier.id, discord_role_id=data.discord_role_id))
    await db.commit()

    return await _get_owned_tier(db, guild_id, tier.id)


async def update_tier(
    db: AsyncSession, guild_id: uuid.UUID, tier_id: uuid.UUID, data: TierUpdate
) -> SubscriptionTier:
    tier = await _get_owned_tier(db, guild_id, tier_id)

    update_data = data.model_dump(exclude_unset=True, exclude={"discord_role_id"})
    for field, value in update_data.items():
        setattr(tier, field, value)

    if data.discord_role_id is not None:
        tier.role_mapping.discord_role_id = data.discord_role_id

    await db.commit()
    return await _get_owned_tier(db, guild_id, tier_id)


async def deactivate_tier(db: AsyncSession, guild_id: uuid.UUID, tier_id: uuid.UUID) -> None:
    tier = await _get_owned_tier(db, guild_id, tier_id)
    tier.active = False
    await db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_subscription_tiers_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/subscription_tiers.py backend/tests/test_subscription_tiers_service.py
git commit -m "feat(backend): add subscription tier service layer"
```

---

### Task 4: Tier API routes

**Files:**
- Create: `backend/app/api/routes/tiers.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_tiers.py`

**Interfaces:**
- Consumes: `get_active_guild`, `get_current_admin_user` (Task 2 / existing `deps.py`); `TierCreate`, `TierUpdate`, `TierOut` (Task 1); `list_tiers`, `create_tier`, `update_tier`, `deactivate_tier` (Task 3).
- Produces: `router = APIRouter(...)` in `app.api.routes.tiers`, registered in `main.py`. Routes: `GET /tiers` (public), `GET /admin/tiers`, `POST /admin/tiers`, `PATCH /admin/tiers/{tier_id}`, `DELETE /admin/tiers/{tier_id}` (admin-only). No later task depends on route internals directly (frontend calls over HTTP).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_tiers.py
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models import User


async def _make_admin_client(client: AsyncClient, db_session) -> AsyncClient:
    user = User(discord_id="1", username="admin", is_admin=True)
    db_session.add(user)
    await db_session.commit()
    client.cookies.set("session", create_access_token(user.id))
    return client


async def test_public_tiers_returns_only_active_tiers(client, db_session):
    admin = await _make_admin_client(client, db_session)
    await admin.post(
        "/admin/tiers", json={"name": "Bronze", "price": 4.99, "duration_days": 30, "discord_role_id": "1"}
    )
    create_response = await admin.post(
        "/admin/tiers", json={"name": "Silver", "price": 9.99, "duration_days": 30, "discord_role_id": "2"}
    )
    silver_id = create_response.json()["data"]["id"]
    await admin.delete(f"/admin/tiers/{silver_id}")
    admin.cookies.clear()

    response = await client.get("/tiers")

    assert response.status_code == 200
    names = [tier["name"] for tier in response.json()["data"]]
    assert names == ["Bronze"]


async def test_admin_tiers_returns_active_and_inactive(client, db_session):
    admin = await _make_admin_client(client, db_session)
    create_response = await admin.post(
        "/admin/tiers", json={"name": "Bronze", "price": 4.99, "duration_days": 30, "discord_role_id": "1"}
    )
    tier_id = create_response.json()["data"]["id"]
    await admin.delete(f"/admin/tiers/{tier_id}")

    response = await admin.get("/admin/tiers")

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["active"] is False


async def test_admin_create_tier_returns_full_tier(client, db_session):
    admin = await _make_admin_client(client, db_session)

    response = await admin.post(
        "/admin/tiers",
        json={"name": "Gold", "description": "VIP perks", "price": 19.99, "duration_days": 30, "discord_role_id": "999"},
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["name"] == "Gold"
    assert body["discord_role_id"] == "999"
    assert body["active"] is True


async def test_admin_update_tier_changes_fields(client, db_session):
    admin = await _make_admin_client(client, db_session)
    create_response = await admin.post(
        "/admin/tiers", json={"name": "Bronze", "price": 4.99, "duration_days": 30, "discord_role_id": "1"}
    )
    tier_id = create_response.json()["data"]["id"]

    response = await admin.patch(f"/admin/tiers/{tier_id}", json={"price": 6.99})

    assert response.status_code == 200
    assert response.json()["data"]["price"] == 6.99


async def test_admin_update_unknown_tier_returns_404(client, db_session):
    admin = await _make_admin_client(client, db_session)

    response = await admin.patch("/admin/tiers/00000000-0000-0000-0000-000000000000", json={"price": 6.99})

    assert response.status_code == 404


async def test_admin_routes_reject_unauthenticated_requests(client):
    response = await client.get("/admin/tiers")

    assert response.status_code == 401


async def test_admin_routes_reject_non_admin_users(client, db_session):
    user = User(discord_id="2", username="member", is_admin=False)
    db_session.add(user)
    await db_session.commit()
    client.cookies.set("session", create_access_token(user.id))

    response = await client.get("/admin/tiers")

    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_tiers.py -v`
Expected: FAIL with 404s (routes don't exist yet)

- [ ] **Step 3: Write the routes**

```python
# backend/app/api/routes/tiers.py
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_guild, get_current_admin_user
from app.db.session import get_db
from app.models import Guild, User
from app.schemas.subscription_tier import TierCreate, TierOut, TierUpdate
from app.services import subscription_tiers as tier_service

router = APIRouter(tags=["tiers"])


@router.get("/tiers")
async def list_public_tiers(
    guild: Guild = Depends(get_active_guild),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tiers = await tier_service.list_tiers(db, guild.id, only_active=True)
    data = [TierOut.from_tier(tier).model_dump(mode="json") for tier in tiers]
    return {"success": True, "data": data, "error": None}


@router.get("/admin/tiers")
async def list_admin_tiers(
    guild: Guild = Depends(get_active_guild),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict:
    tiers = await tier_service.list_tiers(db, guild.id, only_active=False)
    data = [TierOut.from_tier(tier).model_dump(mode="json") for tier in tiers]
    return {"success": True, "data": data, "error": None}


@router.post("/admin/tiers", status_code=status.HTTP_201_CREATED)
async def create_admin_tier(
    payload: TierCreate,
    guild: Guild = Depends(get_active_guild),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict:
    tier = await tier_service.create_tier(db, guild.id, payload)
    return {"success": True, "data": TierOut.from_tier(tier).model_dump(mode="json"), "error": None}


@router.patch("/admin/tiers/{tier_id}")
async def update_admin_tier(
    tier_id: uuid.UUID,
    payload: TierUpdate,
    guild: Guild = Depends(get_active_guild),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict:
    tier = await tier_service.update_tier(db, guild.id, tier_id, payload)
    return {"success": True, "data": TierOut.from_tier(tier).model_dump(mode="json"), "error": None}


@router.delete("/admin/tiers/{tier_id}")
async def deactivate_admin_tier(
    tier_id: uuid.UUID,
    guild: Guild = Depends(get_active_guild),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict:
    await tier_service.deactivate_tier(db, guild.id, tier_id)
    return {"success": True, "data": None, "error": None}
```

Modify `backend/app/main.py`:

```python
from app.api.routes import auth, health, tiers
```

(replace the existing `from app.api.routes import auth, health` line), and add after `app.include_router(auth.router)`:

```python
app.include_router(tiers.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_tiers.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/tiers.py backend/app/main.py backend/tests/test_tiers.py
git commit -m "feat(backend): add subscription tier API routes"
```

---

### Task 5: Seed script

**Files:**
- Create: `backend/app/db/seed.py`
- Test: `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: `get_active_guild` (Task 2), `create_tier` (Task 3), `TierCreate` (Task 1), `AsyncSessionLocal` (existing `app.db.session`).
- Produces: `async def seed_tiers(db: AsyncSession) -> None` (idempotent — re-running with existing tiers is a no-op), plus a `python -m app.db.seed` CLI entrypoint. No later task in this plan depends on this module.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_seed.py
from sqlalchemy import select

from app.db.seed import seed_tiers
from app.models import SubscriptionTier


async def test_seed_tiers_creates_three_active_tiers(db_session):
    await seed_tiers(db_session)

    result = await db_session.execute(select(SubscriptionTier))
    tiers = result.scalars().all()

    assert len(tiers) == 3
    assert all(tier.active for tier in tiers)


async def test_seed_tiers_is_idempotent(db_session):
    await seed_tiers(db_session)
    await seed_tiers(db_session)

    result = await db_session.execute(select(SubscriptionTier))
    tiers = result.scalars().all()

    assert len(tiers) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_seed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db.seed'`

- [ ] **Step 3: Write the seed script**

```python
# backend/app/db/seed.py
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_guild
from app.db.session import AsyncSessionLocal
from app.models import SubscriptionTier
from app.schemas.subscription_tier import TierCreate
from app.services import subscription_tiers as tier_service

SEED_TIERS: list[TierCreate] = [
    TierCreate(
        name="Bronze",
        description="Access to the community lounge\nMonthly community Q&A",
        price=4.99,
        duration_days=30,
        discord_role_id="000000000000000001",
    ),
    TierCreate(
        name="Silver",
        description="Everything in Bronze\nExclusive Silver-only channels\nPriority support",
        price=9.99,
        duration_days=30,
        discord_role_id="000000000000000002",
    ),
    TierCreate(
        name="Gold",
        description="Everything in Silver\nVIP badge and colored name\n1-on-1 support access",
        price=19.99,
        duration_days=30,
        discord_role_id="000000000000000003",
    ),
]


async def seed_tiers(db: AsyncSession) -> None:
    guild = await get_active_guild(db=db)

    existing = await db.execute(select(SubscriptionTier).where(SubscriptionTier.guild_id == guild.id))
    if existing.scalars().first() is not None:
        print("Tiers already seeded, skipping.")
        return

    for order, data in enumerate(SEED_TIERS):
        tier = await tier_service.create_tier(db, guild.id, data)
        tier.display_order = order

    await db.commit()
    print(f"Seeded {len(SEED_TIERS)} tiers.")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await seed_tiers(db)


if __name__ == "__main__":
    asyncio.run(main())
```

Note: `discord_role_id` values above are placeholders (the test Discord server's roles don't exist yet — that's M7). Update them via `PATCH /admin/tiers/{id}` once real role IDs are known.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_seed.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/seed.py backend/tests/test_seed.py
git commit -m "feat(backend): add subscription tier seed script"
```

---

### Task 6: Frontend `Tier` type and `getTiers()` API client

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Consumes: `API_BASE_URL`, `ApiEnvelope<T>` (existing, `frontend/src/lib/api.ts` / `types.ts`).
- Produces: `Tier` interface (`id, name, description, price, currency, duration_days, active, display_order, discord_role_id, created_at`) in `frontend/src/lib/types.ts`; `async function getTiers(): Promise<Tier[]>` in `frontend/src/lib/api.ts`. Later tasks (`TierCard`, pricing page) import `Tier` from `@/lib/types` and `getTiers` from `@/lib/api`.

- [ ] **Step 1: Add the `Tier` type**

Append to `frontend/src/lib/types.ts`:

```typescript
export interface Tier {
  id: string;
  name: string;
  description: string | null;
  price: number;
  currency: string;
  duration_days: number;
  active: boolean;
  display_order: number;
  discord_role_id: string;
  created_at: string;
}
```

- [ ] **Step 2: Add `getTiers()`**

`frontend/src/lib/api.ts` currently has no imports. Add this import at the top of the file:

```typescript
import type { ApiEnvelope, Tier } from "@/lib/types";

export async function getTiers(): Promise<Tier[]> {
  const response = await fetch(`${API_BASE_URL}/tiers`, { cache: "no-store" });

  if (!response.ok) {
    return [];
  }

  const body = (await response.json()) as ApiEnvelope<Tier[]>;
  return body.data ?? [];
}
```

- [ ] **Step 3: Verify it type-checks**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors (the `/pricing` route will still 404 at this point — that's expected, it doesn't exist yet).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat(frontend): add Tier type and getTiers API client"
```

---

### Task 7: `TierCard` component

**Files:**
- Create: `frontend/src/components/tier-card.tsx`

**Interfaces:**
- Consumes: `Tier` (Task 6, `@/lib/types`); `discordLoginUrl` (existing, `@/lib/api`); `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter` (existing, `@/components/ui/card`); `Badge` (existing, `@/components/ui/badge`); `Button` (existing, `@/components/ui/button`); `cn` (existing, `@/lib/utils`).
- Produces: `TierCard({ tier, isLoggedIn, highlighted }: { tier: Tier; isLoggedIn: boolean; highlighted: boolean })`. The pricing page (Task 8) imports this from `@/components/tier-card`.

- [ ] **Step 1: Write the component**

```tsx
// frontend/src/components/tier-card.tsx
import { Check } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { discordLoginUrl } from "@/lib/api";
import type { Tier } from "@/lib/types";
import { cn } from "@/lib/utils";

export function TierCard({
  tier,
  isLoggedIn,
  highlighted,
}: {
  tier: Tier;
  isLoggedIn: boolean;
  highlighted: boolean;
}) {
  const features = (tier.description ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <Card className={cn("flex flex-col", highlighted && "ring-2 ring-accent md:-translate-y-2")}>
      <CardHeader>
        {highlighted && (
          <Badge className="mb-2 w-fit bg-accent text-accent-foreground">Most Popular</Badge>
        )}
        <CardTitle className="text-xl">{tier.name}</CardTitle>
        <CardDescription>
          <span className="text-3xl font-bold text-foreground">${tier.price.toFixed(2)}</span>
          <span className="text-muted-foreground"> / month</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        <ul className="space-y-2 text-sm">
          {features.map((feature, index) => (
            <li key={index} className="flex items-start gap-2">
              <Check className="mt-0.5 size-4 shrink-0 text-primary" />
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      </CardContent>
      <CardFooter>
        {isLoggedIn ? (
          <Button asChild className="w-full">
            <Link href={`/checkout?tier=${tier.id}`}>Subscribe</Link>
          </Button>
        ) : (
          <Button asChild className="w-full">
            <a href={discordLoginUrl()}>Subscribe</a>
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors (the component isn't used anywhere yet, so this only checks it compiles in isolation).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/tier-card.tsx
git commit -m "feat(frontend): add TierCard component"
```

---

### Task 8: Pricing page

**Files:**
- Create: `frontend/src/app/pricing/page.tsx`

**Interfaces:**
- Consumes: `getTiers` (Task 6, `@/lib/api`); `getCurrentUser` (existing, `@/lib/session`); `TierCard` (Task 7, `@/components/tier-card`).
- Produces: the `/pricing` route. Nothing else depends on this file.

- [ ] **Step 1: Write the page**

```tsx
// frontend/src/app/pricing/page.tsx
import { TierCard } from "@/components/tier-card";
import { getTiers } from "@/lib/api";
import { getCurrentUser } from "@/lib/session";

export default async function PricingPage() {
  const [tiers, user] = await Promise.all([getTiers(), getCurrentUser()]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <div className="mb-12 text-center">
        <h1 className="text-4xl font-bold tracking-tight">Choose your plan</h1>
        <p className="mt-3 text-muted-foreground">
          Unlock premium roles in our Discord community.
        </p>
      </div>
      {tiers.length === 0 ? (
        <p className="text-center text-muted-foreground">
          No plans available yet — check back soon.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {tiers.map((tier, index) => (
            <TierCard
              key={tier.id}
              tier={tier}
              isLoggedIn={user !== null}
              highlighted={tiers.length === 3 && index === 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

Run: `cd frontend && npm run build`
Expected: build succeeds; `/pricing` now appears in the build's route list.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pricing/page.tsx
git commit -m "feat(frontend): add pricing page"
```

---

### Task 9: Checkout stub page

**Files:**
- Create: `frontend/src/app/checkout/page.tsx`

**Interfaces:**
- Consumes: nothing project-specific (reads the `tier` search param Next.js provides).
- Produces: the `/checkout` route, linked to from `TierCard` (Task 7). Real checkout logic replaces this in M9/M10/M11.

- [ ] **Step 1: Write the stub page**

```tsx
// frontend/src/app/checkout/page.tsx
export default async function CheckoutPage(props: PageProps<"/checkout">) {
  await props.searchParams;

  return (
    <div className="mx-auto max-w-md px-4 py-24 text-center">
      <h1 className="text-2xl font-bold">Checkout coming soon</h1>
      <p className="mt-3 text-muted-foreground">
        We&apos;re still wiring up payments for this plan. Check back soon!
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

Run: `cd frontend && npm run build`
Expected: build succeeds; `/checkout` now appears in the build's route list.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/checkout/page.tsx
git commit -m "feat(frontend): add checkout stub page"
```

---

### Task 10: End-to-end manual verification

**Files:** none (verification only).

- [ ] **Step 1: Start the backend against a local Postgres (or point `DATABASE_URL` at Supabase per `.env`)**

Run: `cd backend && python -m uvicorn app.main:app --reload`

- [ ] **Step 2: Run the migrations and seed script**

Run: `cd backend && python -m alembic upgrade head && python -m app.db.seed`
Expected output ends with: `Seeded 3 tiers.`

- [ ] **Step 3: Confirm the public endpoint serves the seeded tiers**

Run: `curl http://localhost:8000/tiers`
Expected: `{"success": true, "data": [ ...3 tiers, Bronze/Silver/Gold... ], "error": null}`

- [ ] **Step 4: Start the frontend**

Run: `cd frontend && npm run dev`

- [ ] **Step 5: Manually verify in the browser**

Open `http://localhost:3000/pricing`:
- All 3 tiers render with name, price, and their description lines as bullets.
- The Silver (middle) card has the "Most Popular" badge and accent ring.
- While logged out, each "Subscribe" button links to the Discord OAuth login URL.
- Log in with Discord, return to `/pricing`, confirm each "Subscribe" button now links to `/checkout?tier=<id>` and that page renders the "Checkout coming soon" message.

- [ ] **Step 6: Confirm the empty state (optional but recommended)**

Temporarily deactivate all 3 tiers via `PATCH /admin/tiers/{id}` with `{"active": false}` (using an admin session), reload `/pricing`, confirm the "No plans available yet" message renders instead of an empty grid. Reactivate them afterward (`{"active": true}`) so the seeded data is left in its normal state.
