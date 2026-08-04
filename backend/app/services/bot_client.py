import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

INTERNAL_SECRET_HEADER = "X-Internal-Secret"


class BotClientError(Exception):
    """Raised when the Discord bot's internal API cannot complete a role operation."""


async def _call_role_endpoint(path: str, guild_id: str, discord_user_id: str, role_id: str) -> None:
    settings = get_settings()
    url = f"{settings.bot_internal_api_url}{path}"
    headers = {INTERNAL_SECRET_HEADER: settings.bot_internal_api_secret}
    payload = {"guild_id": guild_id, "user_id": discord_user_id, "role_id": role_id}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        raise BotClientError(f"Could not reach bot internal API at {url}: {exc}") from exc

    if response.status_code != 200:
        raise BotClientError(
            f"Bot internal API returned {response.status_code} for {path}: {response.text}"
        )


async def assign_role(guild_id: str, discord_user_id: str, role_id: str) -> None:
    """Ask the Discord bot to grant `role_id` to `discord_user_id` in `guild_id`."""
    logger.info(
        "Requesting role assignment: guild=%s user=%s role=%s", guild_id, discord_user_id, role_id
    )
    await _call_role_endpoint("/internal/roles/assign", guild_id, discord_user_id, role_id)


async def remove_role(guild_id: str, discord_user_id: str, role_id: str) -> None:
    """Ask the Discord bot to revoke `role_id` from `discord_user_id` in `guild_id`."""
    logger.info(
        "Requesting role removal: guild=%s user=%s role=%s", guild_id, discord_user_id, role_id
    )
    await _call_role_endpoint("/internal/roles/remove", guild_id, discord_user_id, role_id)
