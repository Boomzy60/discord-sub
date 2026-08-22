"""Finds subscriptions past their expiry, revokes their Discord role, and marks them expired.

Run periodically by the scheduler in `app.core.scheduler`, and callable directly
for one-off/manual runs (e.g. tests, an admin-triggered sweep).
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Guild, SubscriptionTier, User
from app.models.enums import SubscriptionStatus
from app.models.subscription import Subscription
from app.services import bot_client
from app.services.subscription_service import get_active_role_ids_for_member, get_role_ids_for_tier_and_below

logger = logging.getLogger(__name__)


async def expire_due_subscriptions(db: AsyncSession) -> int:
    """Mark every active subscription past its expiry as EXPIRED and revoke its role.

    Best-effort per subscription, mirroring `activate_subscription`'s failure
    handling: a bot-side failure (role removal or the notification) is logged
    and does not stop the sweep or prevent the subscription from being marked
    expired, since the bot's `on_member_join`-style catch-up has no equivalent
    for expiry, so we don't want a transient bot outage to leave subscriptions
    stuck ACTIVE forever.

    Returns the number of subscriptions expired.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Subscription).where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.expires_at <= now,
        )
    )
    subscriptions = result.scalars().all()

    for subscription in subscriptions:
        tier = await db.get(SubscriptionTier, subscription.tier_id)
        user = await db.get(User, subscription.user_id)
        guild = await db.get(Guild, tier.guild_id) if tier is not None else None

        if guild is not None and user is not None and tier is not None:
            roles_from_expiring_tier = await get_role_ids_for_tier_and_below(db, tier)
            subscription.status = SubscriptionStatus.EXPIRED

            # Another still-active subscription (e.g. a separately purchased lower tier)
            # may still entitle this member to some of these roles, since roles stack
            # across tiers — only revoke what nothing else still owes them.
            still_owed = set(
                await get_active_role_ids_for_member(
                    db, discord_user_id=user.discord_id, guild_id=guild.guild_id
                )
            )
            for role_id in roles_from_expiring_tier:
                if role_id in still_owed:
                    continue
                try:
                    await bot_client.remove_role(guild.guild_id, user.discord_id, role_id)
                except bot_client.BotClientError as exc:
                    logger.warning(
                        "Role removal failed for user %s in guild %s during expiration: %s",
                        user.discord_id,
                        guild.guild_id,
                        exc,
                    )

            await bot_client.notify_subscription_expired(
                discord_user_id=user.discord_id,
                username=user.username,
                tier_name=tier.name,
                expired_at=subscription.expires_at.isoformat(),
            )
        else:
            logger.warning(
                "Subscription %s is missing its tier, guild, or user; marking expired "
                "without a Discord role revocation",
                subscription.id,
            )
            subscription.status = SubscriptionStatus.EXPIRED

    await db.commit()
    return len(subscriptions)
