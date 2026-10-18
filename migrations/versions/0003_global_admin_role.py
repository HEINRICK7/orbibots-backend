"""Add a global role to users, separate from company memberships.

Revision ID: 0003_global_admin_role
Revises: 0002_user_password_hash
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_global_admin_role"
down_revision: str | None = "0002_user_password_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("global_role", sa.String(length=32), nullable=True))
    op.create_check_constraint(
        "ck_users_global_role",
        "users",
        "global_role IS NULL OR global_role = 'ADMIN'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_global_role", "users", type_="check")
    op.drop_column("users", "global_role")
