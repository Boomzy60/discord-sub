import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import SESSION_COOKIE_NAME, create_access_token
from app.db.session import get_db
from app.models import AuditLog, User
from app.models.enums import AuditAction
from app.schemas.user import UserOut
from app.services.discord_oauth import (
    DiscordOAuthError,
    build_authorize_url,
    exchange_code_for_token,
    fetch_discord_user,
)

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

settings = get_settings()
OAUTH_STATE_COOKIE_NAME = "oauth_state"
_COOKIE_SECURE = settings.environment != "development"


async def _upsert_user_from_discord_profile(db: AsyncSession, profile: dict) -> User:
    discord_id = profile["id"]
    result = await db.execute(select(User).where(User.discord_id == discord_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            discord_id=discord_id,
            username=profile["username"],
            is_admin=discord_id in settings.admin_discord_id_set,
        )
        db.add(user)

    user.username = profile["username"]
    user.global_name = profile.get("global_name")
    user.avatar = profile.get("avatar")
    user.email = profile.get("email")
    user.last_login = datetime.now(timezone.utc)

    await db.flush()
    return user


@router.get("/auth/discord/login")
async def discord_login() -> RedirectResponse:
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(url=build_authorize_url(state))
    response.set_cookie(
        OAUTH_STATE_COOKIE_NAME,
        state,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=600,
    )
    return response


@router.get("/auth/discord/callback")
async def discord_callback(
    code: str = Query(...),
    state: str = Query(...),
    oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if oauth_state is None or oauth_state != state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid OAuth state")

    try:
        token_data = await exchange_code_for_token(code)
        profile = await fetch_discord_user(token_data["access_token"])
    except DiscordOAuthError as exc:
        logger.warning("Discord OAuth failed: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Discord authentication failed") from exc

    user = await _upsert_user_from_discord_profile(db, profile)
    db.add(AuditLog(user_id=user.id, action=AuditAction.LOGIN))
    await db.commit()

    session_token = create_access_token(user.id)
    response = RedirectResponse(url=f"{settings.frontend_base_url}/dashboard")
    response.delete_cookie(OAUTH_STATE_COOKIE_NAME)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.jwt_expires_minutes * 60,
        domain=settings.session_cookie_domain or None,
    )
    return response


@router.post("/auth/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE_NAME, domain=settings.session_cookie_domain or None)
    return {"success": True, "data": None, "error": None}


@router.get("/users/me")
async def get_me(user: User = Depends(get_current_user)) -> dict:
    return {"success": True, "data": UserOut.model_validate(user).model_dump(mode="json"), "error": None}
