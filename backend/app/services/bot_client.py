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


async def notify_subscription_activated(
    *,
    discord_user_id: str,
    username: str,
    tier_name: str,
    price: float,
    currency: str,
    expires_at: str,
) -> None:
    """Ask the bot to post a subscription-activated embed to its log channel.

    Best-effort: a notification failure must never block subscription activation
    (the role has already been granted by the time this is called), so any error
    is logged and swallowed rather than raised.
    """
    settings = get_settings()
    url = f"{settings.bot_internal_api_url}/internal/notify/subscription-activated"
    headers = {INTERNAL_SECRET_HEADER: settings.bot_internal_api_secret}
    payload = {
        "user_id": discord_user_id,
        "username": username,
        "tier_name": tier_name,
        "price": price,
        "currency": currency,
        "expires_at": expires_at,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.warning(
                "Bot internal API returned %s for subscription notification: %s",
                response.status_code,
                response.text,
            )
    except httpx.RequestError as exc:
        logger.warning("Could not reach bot internal API at %s: %s", url, exc)


async def notify_subscription_expired(
    *,
    discord_user_id: str,
    username: str,
    tier_name: str,
    expired_at: str,
) -> None:
    """Ask the bot to post a subscription-expired embed to its log channel.

    Best-effort: same failure handling as `notify_subscription_activated` — a
    notification failure must never block subscription expiration.
    """
    settings = get_settings()
    url = f"{settings.bot_internal_api_url}/internal/notify/subscription-expired"
    headers = {INTERNAL_SECRET_HEADER: settings.bot_internal_api_secret}
    payload = {
        "user_id": discord_user_id,
        "username": username,
        "tier_name": tier_name,
        "expired_at": expired_at,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.warning(
                "Bot internal API returned %s for expiration notification: %s",
                response.status_code,
                response.text,
            )
    except httpx.RequestError as exc:
        logger.warning("Could not reach bot internal API at %s: %s", url, exc)
