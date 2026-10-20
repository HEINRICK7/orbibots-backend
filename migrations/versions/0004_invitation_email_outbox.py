"""Add a retryable outbox for company invitation emails.

Revision ID: 0004_invitation_email_outbox
Revises: 0003_global_admin_role
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_invitation_email_outbox"
down_revision: str | None = "0003_global_admin_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitation_email_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="PENDING", nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SENT', 'FAILED')",
            name="ck_invitation_email_outbox_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_invitation_email_outbox_attempts"),
        sa.ForeignKeyConstraint(
            ["invitation_id"], ["invitations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_invitation_email_outbox_due",
        "invitation_email_outbox",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invitation_email_outbox_due", table_name="invitation_email_outbox"
    )
    op.drop_table("invitation_email_outbox")
