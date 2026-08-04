import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID
from app.models.enums import BillingPeriod


class SubscriptionTier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscription_tiers"
    __table_args__ = (
        Index("idx_subscription_tiers_guild_id", "guild_id"),
        Index("idx_subscription_tiers_active", "active"),
        Index("idx_subscription_tiers_display_order", "display_order"),
    )

    guild_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("guilds.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    billing_period: Mapped[BillingPeriod] = mapped_column(
        Enum(BillingPeriod, name="billingperiod", native_enum=True, validate_strings=True),
        nullable=False,
    )
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="tiers")
    role_mapping: Mapped["TierRoleMapping"] = relationship(back_populates="tier", uselist=False)
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="tier")
