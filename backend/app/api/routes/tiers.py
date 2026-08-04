import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_guild, get_current_admin_user
from app.db.session import get_db
from app.models import Guild, User
from app.schemas.subscription_tier import TierCreate, TierOut, TierUpdate
from app.services import subscription_tiers as tier_service

router = APIRouter(tags=["tiers"])


@router.get("/tiers")
async def list_public_tiers(
    guild: Guild = Depends(get_active_guild),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tiers = await tier_service.list_tiers(db, guild.id, only_active=True)
    data = [TierOut.from_tier(tier).model_dump(mode="json") for tier in tiers]
    return {"success": True, "data": data, "error": None}


@router.get("/admin/tiers")
async def list_admin_tiers(
    guild: Guild = Depends(get_active_guild),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict:
    tiers = await tier_service.list_tiers(db, guild.id, only_active=False)
    data = [TierOut.from_tier(tier).model_dump(mode="json") for tier in tiers]
    return {"success": True, "data": data, "error": None}


@router.post("/admin/tiers", status_code=status.HTTP_201_CREATED)
async def create_admin_tier(
    payload: TierCreate,
    guild: Guild = Depends(get_active_guild),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict:
    tier = await tier_service.create_tier(db, guild.id, payload)
    return {"success": True, "data": TierOut.from_tier(tier).model_dump(mode="json"), "error": None}


@router.patch("/admin/tiers/{tier_id}")
async def update_admin_tier(
    tier_id: uuid.UUID,
    payload: TierUpdate,
    guild: Guild = Depends(get_active_guild),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict:
    tier = await tier_service.update_tier(db, guild.id, tier_id, payload)
    return {"success": True, "data": TierOut.from_tier(tier).model_dump(mode="json"), "error": None}


@router.delete("/admin/tiers/{tier_id}")
async def deactivate_admin_tier(
    tier_id: uuid.UUID,
    guild: Guild = Depends(get_active_guild),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> dict:
    await tier_service.deactivate_tier(db, guild.id, tier_id)
    return {"success": True, "data": None, "error": None}
