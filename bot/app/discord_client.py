import asyncio
import logging

import discord

logger = logging.getLogger(__name__)


class RoleManagerError(Exception):
    """Raised when a Discord role operation cannot be completed."""


class GuildNotFoundError(RoleManagerError):
    """Raised when the bot cannot find the target guild."""


class MemberNotFoundError(RoleManagerError):
    """Raised when the target member is not in the guild."""


class RoleNotFoundError(RoleManagerError):
    """Raised when the target role does not exist in the guild."""


class RoleManagerClient(discord.Client):
    """Discord client that performs role assignment/removal for the backend.

    Subscription and payment decisions are made entirely by the backend; this
    client only executes the resulting Discord-side role mutation.
    """

    def __init__(self, *, intents: discord.Intents) -> None:
        super().__init__(intents=intents)
        self.ready_event = asyncio.Event()

    async def on_ready(self) -> None:
        logger.info("Discord bot connected as %s (guilds: %d)", self.user, len(self.guilds))
        self.ready_event.set()

    async def _resolve_guild(self, guild_id: str) -> discord.Guild:
        guild = self.get_guild(int(guild_id))
        if guild is not None:
            return guild

        try:
            return await self.fetch_guild(int(guild_id))
        except discord.NotFound as exc:
            raise GuildNotFoundError(f"Guild {guild_id} not found") from exc
        except discord.HTTPException as exc:
            raise RoleManagerError(f"Failed to fetch guild {guild_id}: {exc}") from exc

    async def _resolve_member(self, guild: discord.Guild, user_id: str) -> discord.Member:
        member = guild.get_member(int(user_id))
        if member is not None:
            return member

        try:
            return await guild.fetch_member(int(user_id))
        except discord.NotFound as exc:
            raise MemberNotFoundError(f"Member {user_id} not found in guild {guild.id}") from exc
        except discord.HTTPException as exc:
            raise RoleManagerError(f"Failed to fetch member {user_id}: {exc}") from exc

    def _resolve_role(self, guild: discord.Guild, role_id: str) -> discord.Role:
        role = guild.get_role(int(role_id))
        if role is None:
            raise RoleNotFoundError(f"Role {role_id} not found in guild {guild.id}")
        return role

    async def assign_role(self, guild_id: str, user_id: str, role_id: str) -> None:
        """Grant `role_id` to `user_id` in `guild_id`."""
        guild = await self._resolve_guild(guild_id)
        member = await self._resolve_member(guild, user_id)
        role = self._resolve_role(guild, role_id)

        try:
            await member.add_roles(role, reason="Subscription activated")
        except discord.Forbidden as exc:
            raise RoleManagerError(f"Missing permissions to assign role {role_id}") from exc
        except discord.HTTPException as exc:
            raise RoleManagerError(f"Failed to assign role {role_id}: {exc}") from exc

        logger.info("Assigned role %s to user %s in guild %s", role_id, user_id, guild_id)

    async def remove_role(self, guild_id: str, user_id: str, role_id: str) -> None:
        """Revoke `role_id` from `user_id` in `guild_id`."""
        guild = await self._resolve_guild(guild_id)
        member = await self._resolve_member(guild, user_id)
        role = self._resolve_role(guild, role_id)

        try:
            await member.remove_roles(role, reason="Subscription expired")
        except discord.Forbidden as exc:
            raise RoleManagerError(f"Missing permissions to remove role {role_id}") from exc
        except discord.HTTPException as exc:
            raise RoleManagerError(f"Failed to remove role {role_id}: {exc}") from exc

        logger.info("Removed role %s from user %s in guild %s", role_id, user_id, guild_id)
