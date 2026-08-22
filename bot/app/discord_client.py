import asyncio
import logging

import discord
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

INTERNAL_SECRET_HEADER = "X-Internal-Secret"


class RoleManagerError(Exception):
    """Raised when a Discord role operation cannot be completed."""


class GuildNotFoundError(RoleManagerError):
    """Raised when the bot cannot find the target guild."""


class MemberNotFoundError(RoleManagerError):
    """Raised when the target member is not in the guild."""


class RoleNotFoundError(RoleManagerError):
    """Raised when the target role does not exist in the guild."""


class BackendClientError(Exception):
    """Raised when the backend's internal API cannot be reached or returns an error."""


async def fetch_active_role_ids(guild_id: str, user_id: str) -> list[str]:
    """Ask the backend which role ids `user_id` should currently hold in `guild_id`.

    Used on member join to catch up members who subscribed before joining the
    server, since `assign_role` had no member to grant the role to at the time.
    """
    settings = get_settings()
    url = f"{settings.backend_base_url}/internal/subscriptions/active-roles"
    headers = {INTERNAL_SECRET_HEADER: settings.bot_internal_api_secret}
    params = {"discord_user_id": user_id, "guild_id": guild_id}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params, headers=headers)
    except httpx.RequestError as exc:
        raise BackendClientError(f"Could not reach backend at {url}: {exc}") from exc

    if response.status_code != 200:
        raise BackendClientError(
            f"Backend returned {response.status_code} for active-roles: {response.text}"
        )

    return response.json()["data"]["role_ids"]


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

    async def on_member_join(self, member: discord.Member) -> None:
        """Grant any roles `member` already earned by subscribing before joining."""
        guild_id = str(member.guild.id)
        user_id = str(member.id)

        try:
            role_ids = await fetch_active_role_ids(guild_id, user_id)
        except BackendClientError as exc:
            logger.warning("Could not check active subscriptions for new member %s: %s", user_id, exc)
            return

        for role_id in role_ids:
            try:
                await self.assign_role(guild_id, user_id, role_id)
            except RoleManagerError as exc:
                logger.warning(
                    "Failed to retroactively assign role %s to member %s: %s", role_id, user_id, exc
                )

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

    async def send_subscription_notification(
        self,
        *,
        user_id: str,
        username: str,
        tier_name: str,
        price: float,
        currency: str,
        expires_at: str,
    ) -> bool:
        """Post a small embed to the configured log channel for a successful subscription.

        Best-effort: returns False (and logs) instead of raising when no channel is
        configured or the message can't be sent, since a notification failure should
        never block subscription activation.
        """
        channel_id = get_settings().discord_log_channel_id
        if not channel_id:
            logger.info("No log channel configured; skipping subscription notification")
            return False

        channel = self.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await self.fetch_channel(int(channel_id))
            except discord.HTTPException as exc:
                logger.warning("Could not fetch log channel %s: %s", channel_id, exc)
                return False

        embed = discord.Embed(title="New subscription activated", color=discord.Color.purple())
        embed.add_field(name="Member", value=f"<@{user_id}> ({username})", inline=False)
        embed.add_field(name="Tier", value=tier_name, inline=True)
        embed.add_field(name="Price", value=f"{price:.2f} {currency}", inline=True)
        embed.add_field(name="Renews/Expires", value=expires_at, inline=True)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException as exc:
            logger.warning("Failed to send subscription notification to channel %s: %s", channel_id, exc)
            return False

        return True

    async def send_subscription_expired_notification(
        self,
        *,
        user_id: str,
        username: str,
        tier_name: str,
        expired_at: str,
    ) -> bool:
        """Post a small embed to the configured log channel when a subscription expires.

        Best-effort: returns False (and logs) instead of raising, matching
        `send_subscription_notification`'s failure handling.
        """
        channel_id = get_settings().discord_log_channel_id
        if not channel_id:
            logger.info("No log channel configured; skipping expiration notification")
            return False

        channel = self.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await self.fetch_channel(int(channel_id))
            except discord.HTTPException as exc:
                logger.warning("Could not fetch log channel %s: %s", channel_id, exc)
                return False

        embed = discord.Embed(title="Subscription expired", color=discord.Color.red())
        embed.add_field(name="Member", value=f"<@{user_id}> ({username})", inline=False)
        embed.add_field(name="Tier", value=tier_name, inline=True)
        embed.add_field(name="Expired", value=expired_at, inline=True)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException as exc:
            logger.warning("Failed to send expiration notification to channel %s: %s", channel_id, exc)
            return False

        return True
