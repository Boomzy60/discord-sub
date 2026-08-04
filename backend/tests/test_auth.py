from urllib.parse import parse_qs, urlparse

import respx
from httpx import Response
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models import User
from app.services.discord_oauth import DISCORD_TOKEN_URL, DISCORD_USER_URL

DISCORD_PROFILE = {
    "id": "123456789012345678",
    "username": "tester",
    "global_name": "Tester",
    "avatar": "avatarhash",
    "email": "tester@example.com",
}


async def test_discord_login_redirects_with_state_cookie(client):
    response = await client.get("/auth/discord/login")

    assert response.status_code == 307
    assert response.headers["location"].startswith("https://discord.com/oauth2/authorize")
    assert "oauth_state" in response.cookies


async def test_discord_callback_rejects_mismatched_state(client):
    await client.get("/auth/discord/login")

    response = await client.get("/auth/discord/callback", params={"code": "abc", "state": "wrong-state"})

    assert response.status_code == 400


@respx.mock
async def test_discord_callback_creates_user_and_sets_session(client, db_session):
    login_response = await client.get("/auth/discord/login")
    state = parse_qs(urlparse(login_response.headers["location"]).query)["state"][0]

    respx.post(DISCORD_TOKEN_URL).mock(
        return_value=Response(200, json={"access_token": "discord-token", "token_type": "Bearer"})
    )
    respx.get(DISCORD_USER_URL).mock(return_value=Response(200, json=DISCORD_PROFILE))

    response = await client.get(
        "/auth/discord/callback", params={"code": "auth-code", "state": state}
    )

    assert response.status_code == 307
    assert response.headers["location"] == f"{get_settings().frontend_base_url}/dashboard"
    assert "session" in response.cookies

    result = await db_session.execute(select(User).where(User.discord_id == DISCORD_PROFILE["id"]))
    user = result.scalar_one()
    assert user.username == "tester"
    assert user.email == "tester@example.com"


async def test_users_me_requires_authentication(client):
    response = await client.get("/users/me")

    assert response.status_code == 401


async def test_users_me_returns_current_user(client, db_session):
    user = User(discord_id="999888777666555444", username="me")
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(user.id)
    client.cookies.set("session", token)

    response = await client.get("/users/me")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["discord_id"] == "999888777666555444"
