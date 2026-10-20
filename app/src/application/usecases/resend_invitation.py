from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.src.application.gateways.transactions import UnitOfWork
from app.src.domain.dtos.company_onboarding import ResentInvitation
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.entities.company_onboarding.status import AuditOutcome
from app.src.domain.interfaces.adapters.company_onboarding import InvitationTokenIssuer
from app.src.domain.interfaces.gateways.company_onboarding import (
    CompanyOnboardingRepository,
)
from app.src.domain.interfaces.usecases.authentication import RequireGlobalAdmin
from app.src.domain.interfaces.usecases.company_onboarding import ResendInvitation


class ResendInvitationUseCase(ResendInvitation):
    invitation_lifetime = timedelta(hours=24)
    minimum_interval = timedelta(minutes=1)

    def __init__(
        self,
        repository: CompanyOnboardingRepository,
        token_issuer: InvitationTokenIssuer,
        require_global_admin: RequireGlobalAdmin,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._token_issuer = token_issuer
        self._require_global_admin = require_global_admin
        self._unit_of_work = unit_of_work

    def execute(
        self,
        actor: AuthenticatedUser,
        invitation_id: UUID,
    ) -> ResentInvitation:
        self._require_global_admin.execute(actor)
        now = datetime.now(timezone.utc)
        token = self._token_issuer.issue()
        expires_at = now + self.invitation_lifetime
        with self._unit_of_work.transaction():
            resent = self._repository.prepare_invitation_resend(
                invitation_id,
                now,
                token.token_hash,
                expires_at,
                self.minimum_interval,
            )
            self._repository.create_audit_event(
                actor.id,
                resent.company_id,
                "invitation.resend",
                AuditOutcome.SUCCESS,
            )
        return ResentInvitation(
            invitation_id=resent.invitation_id,
            company_id=resent.company_id,
            outbox_id=resent.outbox_id,
            company_name=resent.company_name,
            invited_name=resent.invited_name,
            email=resent.email,
            expires_at=resent.expires_at,
            raw_token=token.raw_token,
        )
