from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Guild(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A Discord server this platform manages subscriptions for.

    Supports the test-server-first workflow: create the production guild row
    and flip `active` without touching application code.
    """

    __tablename__ = "guilds"
    __table_args__ = (Index("idx_guilds_active", "active"),)

    guild_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    guild_name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_discord_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tiers: Mapped[list["SubscriptionTier"]] = relationship(back_populates="guild")
    tier_role_mappings: Mapped[list["TierRoleMapping"]] = relationship(back_populates="guild")
