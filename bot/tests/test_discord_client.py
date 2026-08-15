import discord
import pytest
import respx
from httpx import Response

import app.discord_client as discord_client_module
from app.config import get_settings
from app.discord_client import BackendClientError, RoleManagerClient


class _FakeGuild:
    def __init__(self, guild_id: int) -> None:
        self.id = guild_id


class _FakeMember:
    def __init__(self, member_id: int, guild_id: int) -> None:
        self.id = member_id
        self.guild = _FakeGuild(guild_id)


@pytest.fixture
def role_manager() -> RoleManagerClient:
    return RoleManagerClient(intents=discord.Intents.none())


async def test_on_member_join_assigns_every_active_role(role_manager, monkeypatch):
    async def fake_fetch(guild_id: str, user_id: str) -> list[str]:
        assert (guild_id, user_id) == ("1", "2")
        return ["10", "20"]

    monkeypatch.setattr(discord_client_module, "fetch_active_role_ids", fake_fetch)

    assigned = []

    async def fake_assign_role(guild_id: str, user_id: str, role_id: str) -> None:
        assigned.append((guild_id, user_id, role_id))

    monkeypatch.setattr(role_manager, "assign_role", fake_assign_role)

    await role_manager.on_member_join(_FakeMember(member_id=2, guild_id=1))

    assert assigned == [("1", "2", "10"), ("1", "2", "20")]


async def test_on_member_join_assigns_nothing_without_active_subscription(role_manager, monkeypatch):
    async def fake_fetch(guild_id: str, user_id: str) -> list[str]:
        return []

    monkeypatch.setattr(discord_client_module, "fetch_active_role_ids", fake_fetch)

    calls = []

    async def fake_assign_role(*args) -> None:
        calls.append(args)

    monkeypatch.setattr(role_manager, "assign_role", fake_assign_role)

    await role_manager.on_member_join(_FakeMember(member_id=2, guild_id=1))

    assert calls == []


async def test_on_member_join_swallows_backend_errors(role_manager, monkeypatch):
    async def fake_fetch(guild_id: str, user_id: str) -> list[str]:
        raise BackendClientError("backend unreachable")

    monkeypatch.setattr(discord_client_module, "fetch_active_role_ids", fake_fetch)

    await role_manager.on_member_join(_FakeMember(member_id=2, guild_id=1))


async def test_fetch_active_role_ids_calls_backend_with_shared_secret():
    settings = get_settings()

    with respx.mock:
        route = respx.get(f"{settings.backend_base_url}/internal/subscriptions/active-roles").mock(
            return_value=Response(200, json={"success": True, "data": {"role_ids": ["5"]}, "error": None})
        )

        role_ids = await discord_client_module.fetch_active_role_ids("1", "2")

    assert role_ids == ["5"]
    request = route.calls.last.request
    assert request.headers["X-Internal-Secret"] == settings.bot_internal_api_secret
    assert dict(request.url.params) == {"discord_user_id": "2", "guild_id": "1"}


async def test_fetch_active_role_ids_raises_on_non_200():
    settings = get_settings()

    with respx.mock:
        respx.get(f"{settings.backend_base_url}/internal/subscriptions/active-roles").mock(
            return_value=Response(401, json={"success": False, "data": None, "error": "bad secret"})
        )

        with pytest.raises(BackendClientError):
            await discord_client_module.fetch_active_role_ids("1", "2")
