import uuid

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, INET, JSONB
from app.models.enums import AuditAction


class AuditLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_entity_type", "entity_type"),
        Index("idx_audit_logs_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="auditaction", native_enum=True, validate_strings=True),
        nullable=False,
    )
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    # Mapped to the "metadata" DB column; Python attribute is renamed because
    # `metadata` is reserved on SQLAlchemy's DeclarativeBase.
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship()
