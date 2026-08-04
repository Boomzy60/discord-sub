import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONB
from app.models.enums import PaymentProvider, PaymentStatus


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("idx_payments_status", "status"),
        Index("idx_payments_provider", "provider"),
        Index("idx_payments_created_at", "created_at"),
        Index("idx_payments_payment_reference", "payment_reference"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("subscriptions.id"), nullable=True
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        Enum(PaymentProvider, name="paymentprovider", native_enum=True, validate_strings=True),
        nullable=False,
    )
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    provider_transaction_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    payment_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    webhook_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="paymentstatus", native_enum=True, validate_strings=True),
        default=PaymentStatus.PENDING,
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="payments")
    subscription: Mapped["Subscription"] = relationship(back_populates="payments")
