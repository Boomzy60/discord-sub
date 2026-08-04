"""initial schema baseline

Revision ID: a1b2c3d4
Revises:
Create Date: 2026-08-04

This migration documents, as code, the schema that already exists live on
the project's Supabase database (multi-guild subscriptions, tiers, role
mappings, payments, webhook idempotency log, audit log). Running this
against that database is a no-op since it is already stamped at this
revision; running it against a fresh/empty database bootstraps the same
schema from scratch.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

subscriptionstatus = postgresql.ENUM(
    "PENDING", "ACTIVE", "EXPIRED", "CANCELLED", "FAILED", name="subscriptionstatus"
)
paymentprovider = postgresql.ENUM("PAYPAL", "NOWPAYMENTS", name="paymentprovider")
paymentstatus = postgresql.ENUM(
    "PENDING", "PAID", "FAILED", "REFUNDED", "CANCELLED", "EXPIRED", name="paymentstatus"
)
billingperiod = postgresql.ENUM("MONTHLY", "QUARTERLY", "YEARLY", "LIFETIME", name="billingperiod")
auditaction = postgresql.ENUM(
    "LOGIN",
    "LOGOUT",
    "SUBSCRIPTION_CREATED",
    "SUBSCRIPTION_EXTENDED",
    "SUBSCRIPTION_CANCELLED",
    "ROLE_ASSIGNED",
    "ROLE_REMOVED",
    "PAYMENT_RECEIVED",
    "PAYMENT_FAILED",
    "ADMIN_ACTION",
    "SYSTEM_EVENT",
    name="auditaction",
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (subscriptionstatus, paymentprovider, paymentstatus, billingperiod, auditaction):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "guilds",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("guild_id", sa.Text(), nullable=False),
        sa.Column("guild_name", sa.String(length=100), nullable=False),
        sa.Column("owner_discord_id", sa.Text(), nullable=True),
        sa.Column("default_currency", sa.String(length=10), server_default="USD", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", name="uq_guilds_guild_id"),
    )
    op.create_index("idx_guilds_active", "guilds", ["active"])

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("discord_id", sa.Text(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("global_name", sa.String(length=100), nullable=True),
        sa.Column("avatar", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discord_id", name="uq_users_discord_id"),
    )
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_global_name", "users", ["global_name"])

    op.create_table(
        "subscription_tiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("guild_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="USD", nullable=False),
        sa.Column(
            "billing_period",
            postgresql.ENUM("MONTHLY", "QUARTERLY", "YEARLY", "LIFETIME", name="billingperiod", create_type=False),
            nullable=False,
        ),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guilds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_subscription_tiers_guild_id", "subscription_tiers", ["guild_id"])
    op.create_index("idx_subscription_tiers_active", "subscription_tiers", ["active"])
    op.create_index("idx_subscription_tiers_display_order", "subscription_tiers", ["display_order"])

    op.create_table(
        "tier_role_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("guild_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discord_role_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guilds.id"]),
        sa.ForeignKeyConstraint(["tier_id"], ["subscription_tiers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "tier_id", name="uq_tier_role_mappings_guild_tier"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "ACTIVE", "EXPIRED", "CANCELLED", "FAILED", name="subscriptionstatus", create_type=False
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tier_id"], ["subscription_tiers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("idx_subscriptions_tier_id", "subscriptions", ["tier_id"])
    op.create_index("idx_subscriptions_status", "subscriptions", ["status"])
    op.create_index("idx_subscriptions_expires_at", "subscriptions", ["expires_at"])

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "provider",
            postgresql.ENUM("PAYPAL", "NOWPAYMENTS", name="paymentprovider", create_type=False),
            nullable=False,
        ),
        sa.Column("payment_method", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("provider_transaction_id", sa.Text(), nullable=False),
        sa.Column("payment_reference", sa.Text(), nullable=True),
        sa.Column("invoice_url", sa.Text(), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(), nullable=True),
        sa.Column("webhook_signature", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "PAID", "FAILED", "REFUNDED", "CANCELLED", "EXPIRED", name="paymentstatus", create_type=False
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_transaction_id", name="uq_payments_provider_transaction_id"),
    )
    op.create_index("idx_payments_status", "payments", ["status"])
    op.create_index("idx_payments_provider", "payments", ["provider"])
    op.create_index("idx_payments_created_at", "payments", ["created_at"])
    op.create_index("idx_payments_payment_reference", "payments", ["payment_reference"])

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "provider",
            postgresql.ENUM("PAYPAL", "NOWPAYMENTS", name="paymentprovider", create_type=False),
            nullable=False,
        ),
        sa.Column("provider_event_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("processed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_event_id", name="uq_webhook_events_provider_event_id"),
    )
    op.create_index("idx_webhook_events_provider", "webhook_events", ["provider"])
    op.create_index("idx_webhook_events_processed", "webhook_events", ["processed"])
    op.create_index("idx_webhook_events_created_at", "webhook_events", ["created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "action",
            postgresql.ENUM(
                "LOGIN",
                "LOGOUT",
                "SUBSCRIPTION_CREATED",
                "SUBSCRIPTION_EXTENDED",
                "SUBSCRIPTION_CANCELLED",
                "ROLE_ASSIGNED",
                "ROLE_REMOVED",
                "PAYMENT_RECEIVED",
                "PAYMENT_FAILED",
                "ADMIN_ACTION",
                "SYSTEM_EVENT",
                name="auditaction",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index("idx_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("idx_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("webhook_events")
    op.drop_table("payments")
    op.drop_table("subscriptions")
    op.drop_table("tier_role_mappings")
    op.drop_table("subscription_tiers")
    op.drop_table("users")
    op.drop_table("guilds")

    bind = op.get_bind()
    for enum_type in (auditaction, billingperiod, paymentstatus, paymentprovider, subscriptionstatus):
        enum_type.drop(bind, checkfirst=True)
