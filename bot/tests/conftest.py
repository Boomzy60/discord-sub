import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app import internal_api as internal_api_module
from app.internal_api import create_internal_api

TEST_INTERNAL_SECRET = "test-secret"


class FakeSettings:
    bot_internal_api_secret = TEST_INTERNAL_SECRET


class FakeDiscordClient:
    """Stands in for RoleManagerClient so tests never touch the real Discord API."""

    def __init__(self) -> None:
        self.ready_event = asyncio.Event()
        self.ready_event.set()
        self.assign_calls: list[tuple[str, str, str]] = []
        self.remove_calls: list[tuple[str, str, str]] = []
        self.assign_exception: Exception | None = None
        self.remove_exception: Exception | None = None

    async def assign_role(self, guild_id: str, user_id: str, role_id: str) -> None:
        self.assign_calls.append((guild_id, user_id, role_id))
        if self.assign_exception is not None:
            raise self.assign_exception

    async def remove_role(self, guild_id: str, user_id: str, role_id: str) -> None:
        self.remove_calls.append((guild_id, user_id, role_id))
        if self.remove_exception is not None:
            raise self.remove_exception


@pytest.fixture(autouse=True)
def _patch_internal_secret(monkeypatch):
    monkeypatch.setattr(internal_api_module, "get_settings", lambda: FakeSettings())


@pytest.fixture
def auth_headers() -> dict:
    return {"X-Internal-Secret": TEST_INTERNAL_SECRET}


@pytest.fixture
def fake_discord_client() -> FakeDiscordClient:
    return FakeDiscordClient()


@pytest.fixture
async def client(fake_discord_client):
    app = create_internal_api(fake_discord_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
