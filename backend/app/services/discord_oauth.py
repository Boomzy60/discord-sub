from urllib.parse import urlencode

import httpx

from app.core.config import get_settings

settings = get_settings()

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = f"{DISCORD_API_BASE}/oauth2/token"
DISCORD_USER_URL = f"{DISCORD_API_BASE}/users/@me"

OAUTH_SCOPES = "identify email"


class DiscordOAuthError(Exception):
    """Raised when Discord's OAuth token exchange or user lookup fails."""


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.discord_redirect_uri,
        "response_type": "code",
        "scope": OAUTH_SCOPES,
        "state": state,
        "prompt": "consent",
    }
    return f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> dict:
    data = {
        "client_id": settings.discord_client_id,
        "client_secret": settings.discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.discord_redirect_uri,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient() as client:
        response = await client.post(DISCORD_TOKEN_URL, data=data, headers=headers)

    if response.status_code != 200:
        raise DiscordOAuthError(f"Token exchange failed: {response.status_code} {response.text}")

    return response.json()


async def fetch_discord_user(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(DISCORD_USER_URL, headers=headers)

    if response.status_code != 200:
        raise DiscordOAuthError(f"Fetching Discord user failed: {response.status_code} {response.text}")

    return response.json()
