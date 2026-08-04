import uuid

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID


class TierRoleMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tier_role_mappings"
    __table_args__ = (UniqueConstraint("guild_id", "tier_id", name="uq_tier_role_mappings_guild_tier"),)

    guild_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("guilds.id"), nullable=False)
    tier_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("subscription_tiers.id"), nullable=False
    )
    discord_role_id: Mapped[str] = mapped_column(Text, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="tier_role_mappings")
    tier: Mapped["SubscriptionTier"] = relationship(back_populates="role_mapping")
