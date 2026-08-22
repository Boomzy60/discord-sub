import json

import httpx
import pytest
import respx
from httpx import Response

from app.core.config import get_settings
from app.services.bot_client import (
    BotClientError,
    assign_role,
    notify_subscription_expired,
    remove_role,
)


@respx.mock
async def test_assign_role_posts_to_bot_internal_api_with_shared_secret():
    settings = get_settings()
    route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": True}, "error": None})
    )

    await assign_role("111", "222", "333")

    assert route.called
    request = route.calls.last.request
    assert request.headers["X-Internal-Secret"] == settings.bot_internal_api_secret
    assert json.loads(request.content) == {"guild_id": "111", "user_id": "222", "role_id": "333"}


@respx.mock
async def test_remove_role_posts_to_bot_internal_api():
    settings = get_settings()
    route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/remove").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": False}, "error": None})
    )

    await remove_role("111", "222", "333")

    assert route.called


@respx.mock
async def test_assign_role_raises_bot_client_error_on_non_200_response():
    settings = get_settings()
    respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        return_value=Response(404, json={"success": False, "data": None, "error": "Member not found"})
    )

    with pytest.raises(BotClientError):
        await assign_role("111", "222", "333")


@respx.mock
async def test_assign_role_raises_bot_client_error_when_bot_unreachable():
    settings = get_settings()
    respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with pytest.raises(BotClientError):
        await assign_role("111", "222", "333")


@respx.mock
async def test_notify_subscription_expired_posts_to_bot_internal_api():
    settings = get_settings()
    route = respx.post(f"{settings.bot_internal_api_url}/internal/notify/subscription-expired").mock(
        return_value=Response(200, json={"success": True, "data": {"sent": True}, "error": None})
    )

    await notify_subscription_expired(
        discord_user_id="222", username="tester", tier_name="Gold", expired_at="2026-09-01T00:00:00+00:00"
    )

    assert route.called
    request = route.calls.last.request
    assert request.headers["X-Internal-Secret"] == settings.bot_internal_api_secret
    assert json.loads(request.content) == {
        "user_id": "222",
        "username": "tester",
        "tier_name": "Gold",
        "expired_at": "2026-09-01T00:00:00+00:00",
    }


@respx.mock
async def test_notify_subscription_expired_swallows_errors_when_bot_unreachable():
    settings = get_settings()
    respx.post(f"{settings.bot_internal_api_url}/internal/notify/subscription-expired").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    await notify_subscription_expired(
        discord_user_id="222", username="tester", tier_name="Gold", expired_at="2026-09-01T00:00:00+00:00"
    )
