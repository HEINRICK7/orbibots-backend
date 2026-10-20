from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.company_onboarding.status import (
    AuditOutcome,
    CompanyStatus,
    InvitationStatus,
)
from app.src.domain.interfaces.gateways.company_onboarding import (
    CompanyOnboardingRepository,
)
from app.src.infra.adapters.persistence.company_onboarding_models import (
    AuditEvent,
    Company,
    Invitation,
)


class SqlAlchemyCompanyOnboardingRepository(CompanyOnboardingRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_company(
        self, name: str, status: CompanyStatus, created_at: datetime
    ) -> UUID:
        company = Company(name=name, status=status, created_at=created_at)
        self._session.add(company)
        self._session.flush()
        return company.id

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
    ) -> UUID:
        invitation = Invitation(
            company_id=company_id,
            invited_name=invited_name,
            email=email,
            phone=phone,
            intended_role=intended_role,
            token_hash=token_hash,
            status=status,
            expires_at=expires_at,
            created_at=created_at,
        )
        self._session.add(invitation)
        self._session.flush()
        return invitation.id

    def create_audit_event(
        self,
        actor_user_id: UUID | None,
        company_id: UUID | None,
        action: str,
        outcome: AuditOutcome,
    ) -> None:
        self._session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                company_id=company_id,
                action=action,
                outcome=outcome.value,
            )
        )
        self._session.flush()
