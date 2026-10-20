from datetime import datetime, timezone
from uuid import UUID

from app.src.application.gateways.transactions import UnitOfWork
from app.src.domain.dtos.company_onboarding import RevokedInvitation
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.entities.company_onboarding.status import AuditOutcome
from app.src.domain.interfaces.gateways.company_onboarding import (
    CompanyOnboardingRepository,
)
from app.src.domain.interfaces.usecases.authentication import RequireGlobalAdmin
from app.src.domain.interfaces.usecases.company_onboarding import RevokeInvitation


class RevokeInvitationUseCase(RevokeInvitation):
    def __init__(
        self,
        repository: CompanyOnboardingRepository,
        require_global_admin: RequireGlobalAdmin,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._require_global_admin = require_global_admin
        self._unit_of_work = unit_of_work

    def execute(
        self,
        actor: AuthenticatedUser,
        invitation_id: UUID,
    ) -> RevokedInvitation:
        self._require_global_admin.execute(actor)
        now = datetime.now(timezone.utc)
        with self._unit_of_work.transaction():
            revoked = self._repository.revoke_invitation(invitation_id, now)
            self._repository.create_audit_event(
                actor.id,
                revoked.company_id,
                "invitation.revoke",
                AuditOutcome.SUCCESS,
            )
        return revoked
