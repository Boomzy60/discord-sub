from sqlalchemy import select

from app.api.deps import get_active_guild
from app.core.config import get_settings
from app.models import Guild


async def test_get_active_guild_creates_guild_when_missing(db_session):
    guild = await get_active_guild(db=db_session)

    assert guild.guild_id == get_settings().discord_guild_id
    assert guild.active is True

    result = await db_session.execute(select(Guild))
    assert len(result.scalars().all()) == 1


async def test_get_active_guild_returns_existing_guild(db_session):
    first = await get_active_guild(db=db_session)
    second = await get_active_guild(db=db_session)

    assert first.id == second.id

    result = await db_session.execute(select(Guild))
    assert len(result.scalars().all()) == 1
