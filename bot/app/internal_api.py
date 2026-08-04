import asyncio
import hmac
import logging

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.discord_client import (
    GuildNotFoundError,
    MemberNotFoundError,
    RoleManagerClient,
    RoleManagerError,
    RoleNotFoundError,
)

logger = logging.getLogger(__name__)

READY_TIMEOUT_SECONDS = 15


class RoleActionRequest(BaseModel):
    guild_id: str
    user_id: str
    role_id: str


class SubscriptionNotificationRequest(BaseModel):
    user_id: str
    username: str
    tier_name: str
    price: float
    currency: str
    expires_at: str


def verify_internal_secret(x_internal_secret: str | None = Header(default=None)) -> None:
    expected = get_settings().bot_internal_api_secret
    if not expected or not x_internal_secret or not hmac.compare_digest(x_internal_secret, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal API secret")


def create_internal_api(discord_client: RoleManagerClient) -> FastAPI:
    """Build the internal API the backend uses to drive Discord role changes.

    `discord_client` is injected rather than imported globally so the API can
    be exercised in tests against a fake client with no real Discord connection.
    """
    app = FastAPI(title="Discord Bot Internal API")

    async def _wait_until_ready() -> None:
        try:
            await asyncio.wait_for(discord_client.ready_event.wait(), timeout=READY_TIMEOUT_SECONDS)
        except asyncio.TimeoutError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "Discord client is not ready"
            ) from exc

    @app.get("/internal/health")
    async def health() -> dict:
        return {
            "success": True,
            "data": {"status": "ok", "discord_ready": discord_client.ready_event.is_set()},
            "error": None,
        }

    @app.post("/internal/roles/assign", dependencies=[Depends(verify_internal_secret)])
    async def assign_role(payload: RoleActionRequest) -> dict:
        await _wait_until_ready()
        try:
            await discord_client.assign_role(payload.guild_id, payload.user_id, payload.role_id)
        except (GuildNotFoundError, MemberNotFoundError, RoleNotFoundError) as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        except RoleManagerError as exc:
            logger.error("Role assignment failed: %s", exc)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
        return {"success": True, "data": {"assigned": True}, "error": None}

    @app.post("/internal/roles/remove", dependencies=[Depends(verify_internal_secret)])
    async def remove_role(payload: RoleActionRequest) -> dict:
        await _wait_until_ready()
        try:
            await discord_client.remove_role(payload.guild_id, payload.user_id, payload.role_id)
        except (GuildNotFoundError, MemberNotFoundError, RoleNotFoundError) as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        except RoleManagerError as exc:
            logger.error("Role removal failed: %s", exc)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
        return {"success": True, "data": {"assigned": False}, "error": None}

    @app.post(
        "/internal/notify/subscription-activated",
        dependencies=[Depends(verify_internal_secret)],
    )
    async def notify_subscription_activated(payload: SubscriptionNotificationRequest) -> dict:
        await _wait_until_ready()
        sent = await discord_client.send_subscription_notification(
            user_id=payload.user_id,
            username=payload.username,
            tier_name=payload.tier_name,
            price=payload.price,
            currency=payload.currency,
            expires_at=payload.expires_at,
        )
        return {"success": True, "data": {"sent": sent}, "error": None}

    return app
