from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.src.domain.dtos.company_onboarding import (
    AcceptedInvitation,
    InvitationAcceptanceContext,
    InvitationEmailJob,
    InvitationSummary,
    PreparedInvitationResend,
    ResentInvitation,
    RevokedInvitation,
)
from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.company_onboarding.status import (
    AuditOutcome,
    CompanyStatus,
    InvitationStatus,
)


class CompanyOnboardingRepository(Protocol):
    def create_company(
        self, name: str, status: CompanyStatus, created_at: datetime
    ) -> UUID: ...

    def create_invitation(
        self,
        company_id: UUID,
        invited_name: str,
        email: str,
        phone: str | None,
        intended_role: CompanyRole,
        token_hash: str,
        status: InvitationStatus,
        expires_at: datetime,
        created_at: datetime,
    ) -> UUID: ...

    def create_audit_event(
        self,
        actor_user_id: UUID | None,
        company_id: UUID | None,
        action: str,
        outcome: AuditOutcome,
    ) -> None: ...

    def create_invitation_outbox_event(
        self, invitation_id: UUID, created_at: datetime
    ) -> UUID: ...

    def get_invitation_acceptance_context(
        self, token_hash: str, now: datetime
    ) -> InvitationAcceptanceContext: ...

    def accept_invitation(
        self, token_hash: str, now: datetime
    ) -> AcceptedInvitation: ...

    def prepare_invitation_resend(
        self,
        invitation_id: UUID,
        now: datetime,
        token_hash: str,
        expires_at: datetime,
        minimum_interval: timedelta,
    ) -> PreparedInvitationResend: ...

    def revoke_invitation(
        self, invitation_id: UUID, now: datetime
    ) -> RevokedInvitation: ...

    def list_company_invitations(
        self, company_id: UUID
    ) -> tuple[InvitationSummary, ...]: ...


class InvitationOutboxRepository(Protocol):
    def claim_invitation_email(
        self,
        outbox_id: UUID,
        now: datetime,
        stale_before: datetime,
        token_hash: str | None = None,
        expires_at: datetime | None = None,
    ) -> InvitationEmailJob | None: ...

    def mark_invitation_email_sent(self, outbox_id: UUID, delivered_at: datetime) -> None: ...

    def schedule_invitation_email_retry(
        self, outbox_id: UUID, attempted_at: datetime, retry_at: datetime
    ) -> None: ...

    def list_pending_invitation_emails(
        self, now: datetime, limit: int
    ) -> tuple[UUID, ...]: ...
