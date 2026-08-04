from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONB
from app.models.enums import PaymentProvider


class WebhookEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Records every inbound payment webhook for idempotent processing and audit."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        Index("idx_webhook_events_provider", "provider"),
        Index("idx_webhook_events_processed", "processed"),
        Index("idx_webhook_events_created_at", "created_at"),
    )

    provider: Mapped[PaymentProvider] = mapped_column(
        Enum(PaymentProvider, name="paymentprovider", native_enum=True, validate_strings=True),
        nullable=False,
    )
    provider_event_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
