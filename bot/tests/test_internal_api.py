from app.discord_client import MemberNotFoundError, RoleManagerError


async def test_health_reports_discord_ready_state(client):
    response = await client.get("/internal/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"status": "ok", "discord_ready": True},
        "error": None,
    }


async def test_assign_role_rejects_missing_secret(client):
    response = await client.post(
        "/internal/roles/assign", json={"guild_id": "1", "user_id": "2", "role_id": "3"}
    )

    assert response.status_code == 401


async def test_assign_role_rejects_wrong_secret(client):
    response = await client.post(
        "/internal/roles/assign",
        json={"guild_id": "1", "user_id": "2", "role_id": "3"},
        headers={"X-Internal-Secret": "wrong-secret"},
    )

    assert response.status_code == 401


async def test_assign_role_calls_discord_client(client, fake_discord_client, auth_headers):
    response = await client.post(
        "/internal/roles/assign",
        json={"guild_id": "1", "user_id": "2", "role_id": "3"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"assigned": True}, "error": None}
    assert fake_discord_client.assign_calls == [("1", "2", "3")]


async def test_remove_role_calls_discord_client(client, fake_discord_client, auth_headers):
    response = await client.post(
        "/internal/roles/remove",
        json={"guild_id": "1", "user_id": "2", "role_id": "3"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"assigned": False}, "error": None}
    assert fake_discord_client.remove_calls == [("1", "2", "3")]


async def test_assign_role_returns_404_when_member_not_found(client, fake_discord_client, auth_headers):
    fake_discord_client.assign_exception = MemberNotFoundError("Member 2 not found in guild 1")

    response = await client.post(
        "/internal/roles/assign",
        json={"guild_id": "1", "user_id": "2", "role_id": "3"},
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_assign_role_returns_502_on_generic_role_manager_error(
    client, fake_discord_client, auth_headers
):
    fake_discord_client.assign_exception = RoleManagerError("Missing permissions to assign role 3")

    response = await client.post(
        "/internal/roles/assign",
        json={"guild_id": "1", "user_id": "2", "role_id": "3"},
        headers=auth_headers,
    )

    assert response.status_code == 502


async def test_remove_role_returns_404_when_member_not_found(client, fake_discord_client, auth_headers):
    fake_discord_client.remove_exception = MemberNotFoundError("Member 2 not found in guild 1")

    response = await client.post(
        "/internal/roles/remove",
        json={"guild_id": "1", "user_id": "2", "role_id": "3"},
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_notify_subscription_activated_rejects_missing_secret(client):
    response = await client.post(
        "/internal/notify/subscription-activated",
        json={
            "user_id": "2",
            "username": "tester",
            "tier_name": "Gold",
            "price": 19.99,
            "currency": "USD",
            "expires_at": "2026-09-01T00:00:00+00:00",
        },
    )

    assert response.status_code == 401


async def test_notify_subscription_activated_calls_discord_client(
    client, fake_discord_client, auth_headers
):
    payload = {
        "user_id": "2",
        "username": "tester",
        "tier_name": "Gold",
        "price": 19.99,
        "currency": "USD",
        "expires_at": "2026-09-01T00:00:00+00:00",
    }

    response = await client.post(
        "/internal/notify/subscription-activated", json=payload, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"sent": True}, "error": None}
    assert fake_discord_client.notify_calls == [payload]


async def test_notify_subscription_activated_reports_when_not_sent(
    client, fake_discord_client, auth_headers
):
    fake_discord_client.notify_result = False

    response = await client.post(
        "/internal/notify/subscription-activated",
        json={
            "user_id": "2",
            "username": "tester",
            "tier_name": "Gold",
            "price": 19.99,
            "currency": "USD",
            "expires_at": "2026-09-01T00:00:00+00:00",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"sent": False}, "error": None}


async def test_notify_subscription_expired_rejects_missing_secret(client):
    response = await client.post(
        "/internal/notify/subscription-expired",
        json={
            "user_id": "2",
            "username": "tester",
            "tier_name": "Gold",
            "expired_at": "2026-09-01T00:00:00+00:00",
        },
    )

    assert response.status_code == 401


async def test_notify_subscription_expired_calls_discord_client(
    client, fake_discord_client, auth_headers
):
    payload = {
        "user_id": "2",
        "username": "tester",
        "tier_name": "Gold",
        "expired_at": "2026-09-01T00:00:00+00:00",
    }

    response = await client.post(
        "/internal/notify/subscription-expired", json=payload, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"sent": True}, "error": None}
    assert fake_discord_client.expired_notify_calls == [payload]


async def test_notify_subscription_expired_reports_when_not_sent(
    client, fake_discord_client, auth_headers
):
    fake_discord_client.expired_notify_result = False

    response = await client.post(
        "/internal/notify/subscription-expired",
        json={
            "user_id": "2",
            "username": "tester",
            "tier_name": "Gold",
            "expired_at": "2026-09-01T00:00:00+00:00",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"sent": False}, "error": None}
