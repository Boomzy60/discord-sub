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
