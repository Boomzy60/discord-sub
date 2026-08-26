"""Add STRIPE to the paymentprovider enum.

Revision ID: b2c3d4e5
Revises: a1b2c3d4
Create Date: 2026-08-26

Postgres enum values can only be added, never removed, inside a transaction-safe
way via ALTER TYPE ... ADD VALUE; there is no corresponding "remove value" so
downgrade is a no-op (matches Postgres' own limitation, not an oversight).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b2c3d4e5"
down_revision: Union[str, None] = "a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block in Postgres.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE paymentprovider ADD VALUE IF NOT EXISTS 'STRIPE'")


def downgrade() -> None:
    # Postgres does not support removing a value from an enum type.
    pass
