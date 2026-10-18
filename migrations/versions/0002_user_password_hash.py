"""Add nullable password hashes to users.

Revision ID: 0002_user_password_hash
Revises: 0001_initial_onboarding
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_user_password_hash"
down_revision: str | None = "0001_initial_onboarding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
