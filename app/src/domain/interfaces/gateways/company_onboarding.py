from datetime import datetime
from typing import Protocol
from uuid import UUID

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
