import asyncio
import logging
import sys

import discord
import uvicorn

from app.config import get_settings
from app.discord_client import RoleManagerClient
from app.internal_api import create_internal_api

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
        force=True,
    )

    intents = discord.Intents.default()
    # Privileged intent, required to receive on_member_join; must also be enabled under
    # "Server Members Intent" on the Bot page of the Discord Developer Portal.
    intents.members = True
    discord_client = RoleManagerClient(intents=intents)

    internal_api = create_internal_api(discord_client)
    server = uvicorn.Server(
        uvicorn.Config(
            internal_api,
            host=settings.bot_internal_api_host,
            port=settings.bot_internal_api_port,
            log_level=settings.log_level.lower(),
        )
    )

    logger.info("Starting Discord bot and internal role API")
    await asyncio.gather(
        discord_client.start(settings.discord_bot_token),
        server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
