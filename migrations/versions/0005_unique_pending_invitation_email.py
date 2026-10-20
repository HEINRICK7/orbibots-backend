"""Prevent duplicate pending company-admin invitations by email.

Revision ID: 0005_pending_email_unique
Revises: 0004_invitation_email_outbox
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_pending_email_unique"
down_revision: str | None = "0004_invitation_email_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_invitations_pending_email_lower",
        "invitations",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
        sqlite_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_invitations_pending_email_lower",
        table_name="invitations",
    )
