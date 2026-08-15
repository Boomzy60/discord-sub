from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_bot_internal_secret
from app.db.session import get_db
from app.services import subscription_service

router = APIRouter(tags=["internal"], dependencies=[Depends(verify_bot_internal_secret)])


@router.get("/internal/subscriptions/active-roles")
async def get_active_roles(
    discord_user_id: str,
    guild_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the Discord role ids `discord_user_id` should currently hold in `guild_id`.

    Called by the bot's member-join handler to grant roles retroactively to members
    who subscribed before joining the Discord server.
    """
    role_ids = await subscription_service.get_active_role_ids_for_member(
        db, discord_user_id=discord_user_id, guild_id=guild_id
    )
    return {"success": True, "data": {"role_ids": role_ids}, "error": None}
