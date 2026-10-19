import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.company_onboarding.membership_scope import MembershipScope
from src.infrastructure.persistence.database import Base


membership_scope_type = Enum(
    MembershipScope,
    name="membership_scope",
    values_callable=lambda enum_type: [item.value for item in enum_type],
)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_ACTIVATION', 'ACTIVE', 'SUSPENDED')",
            name="ck_companies_status",
        ),
        CheckConstraint("length(trim(name)) > 0", name="ck_companies_name_not_empty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING_ACTIVATION", server_default="PENDING_ACTIVATION"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["Membership"]] = relationship(back_populates="company")
    invitations: Mapped[list["Invitation"]] = relationship(back_populates="company")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('COMPANY_ADMIN', 'AGENT_EDITOR')", name="ck_memberships_role"
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'REVOKED')", name="ck_memberships_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[MembershipScope | None] = mapped_column(membership_scope_type)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    company: Mapped[Company] = relationship(back_populates="memberships")
    user: Mapped["UserRecord"] = relationship(back_populates="memberships")


Index(
    "uq_memberships_active_user_company",
    Membership.user_id,
    Membership.company_id,
    unique=True,
    postgresql_where=text("status = 'ACTIVE'"),
)


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint(
            "intended_role IN ('COMPANY_ADMIN', 'AGENT_EDITOR')",
            name="ck_invitations_intended_role",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'EXPIRED', 'REVOKED')",
            name="ck_invitations_status",
        ),
        CheckConstraint(
            "length(trim(invited_name)) > 0", name="ck_invitations_name_not_empty"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    invited_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    intended_role: Mapped[str] = mapped_column(String(32), nullable=False)
    intended_scope: Mapped[MembershipScope | None] = mapped_column(membership_scope_type)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING", server_default="PENDING"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship(back_populates="invitations")


Index(
    "uq_invitations_company_email_lower",
    Invitation.company_id,
    func.lower(Invitation.email),
    unique=True,
)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('SUCCESS', 'DENIED', 'FAILURE')", name="ck_audit_events_outcome"
        ),
        CheckConstraint(
            "length(trim(action)) > 0", name="ck_audit_events_action_not_empty"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
