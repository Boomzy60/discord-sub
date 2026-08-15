import hmac
import uuid

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import SESSION_COOKIE_NAME, decode_access_token
from app.db.session import get_db
from app.models import Guild, User


async def get_current_user(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = decode_access_token(session)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    return user


async def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


async def verify_bot_internal_secret(x_internal_secret: str | None = Header(default=None)) -> None:
    expected = get_settings().bot_internal_api_secret
    if not expected or not x_internal_secret or not hmac.compare_digest(x_internal_secret, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal API secret")


async def get_active_guild(db: AsyncSession = Depends(get_db)) -> Guild:
    settings = get_settings()
    result = await db.execute(select(Guild).where(Guild.guild_id == settings.discord_guild_id))
    guild = result.scalar_one_or_none()
    if guild is None:
        guild = Guild(guild_id=settings.discord_guild_id, guild_name="Discord Server", active=True)
        db.add(guild)
        await db.commit()
        await db.refresh(guild)
    return guild
