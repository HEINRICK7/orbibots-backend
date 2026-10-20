from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.company_onboarding.status import (
    CompanyStatus,
    InvitationStatus,
    OutboxStatus,
)


@dataclass(frozen=True)
class CompanyInvitationRequest:
    company_name: str
    admin_name: str
    email: str
    phone: str | None = None


@dataclass(frozen=True)
class IssuedInvitationToken:
    raw_token: str = field(repr=False)
    token_hash: str


@dataclass(frozen=True)
class ProvisionCompanyResult:
    company_id: UUID
    invitation_id: UUID
    outbox_id: UUID
    company_name: str
    admin_name: str
    email: str
    expires_at: datetime
    raw_token: str = field(repr=False)


@dataclass(frozen=True)
class InvitationDetails:
    id: UUID
    company_id: UUID
    company_name: str
    invited_name: str
    email: str
    phone: str | None
    intended_role: CompanyRole
    token_hash: str
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class InvitationSummary:
    id: UUID
    company_id: UUID
    company_name: str
    invited_name: str
    email: str
    intended_role: CompanyRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class CompanyOnboardingSummary:
    id: UUID
    name: str
    status: CompanyStatus
    created_at: datetime
    activated_at: datetime | None
    invitations: tuple[InvitationSummary, ...]


@dataclass(frozen=True)
class InvitationEmailJob:
    outbox_id: UUID
    invitation_id: UUID
    company_name: str
    invited_name: str
    email: str
    status: OutboxStatus
    attempts: int
    expires_at: datetime


@dataclass(frozen=True)
class InvitationEmailMessage:
    recipient: str
    subject: str
    text_body: str = field(repr=False)
    html_body: str = field(repr=False)
    message_id: str


@dataclass(frozen=True)
class EmailDispatchResult:
    sent: bool


@dataclass(frozen=True)
class InvitationAcceptanceContext:
    invitation_id: UUID
    company_id: UUID
    company_name: str
    invited_name: str
    email: str
    intended_role: CompanyRole
    expires_at: datetime


@dataclass(frozen=True)
class AcceptedInvitation:
    invitation_id: UUID
    company_id: UUID
    company_name: str
    user_id: UUID


@dataclass(frozen=True)
class AcceptedInvitationSession:
    invitation_id: UUID
    company_id: UUID
    company_name: str
    user_id: UUID
    access_token: str = field(repr=False)
    expires_in: int


@dataclass(frozen=True)
class ResentInvitation:
    invitation_id: UUID
    company_id: UUID
    outbox_id: UUID
    company_name: str
    invited_name: str
    email: str
    expires_at: datetime
    raw_token: str = field(repr=False)


@dataclass(frozen=True)
class PreparedInvitationResend:
    invitation_id: UUID
    company_id: UUID
    outbox_id: UUID
    company_name: str
    invited_name: str
    email: str
    expires_at: datetime


@dataclass(frozen=True)
class RevokedInvitation:
    invitation_id: UUID
    company_id: UUID
