from datetime import datetime, timezone

from app.src.application.gateways.transactions import UnitOfWork
from app.src.domain.dtos.company_onboarding import InvitationAcceptanceContext
from app.src.domain.entities.company_onboarding.errors import InvitationNotFoundError
from app.src.domain.interfaces.adapters.company_onboarding import InvitationTokenIssuer
from app.src.domain.interfaces.gateways.company_onboarding import (
    CompanyOnboardingRepository,
)
from app.src.domain.interfaces.usecases.company_onboarding import (
    GetInvitationAcceptanceContext,
)


class GetInvitationAcceptanceContextUseCase(GetInvitationAcceptanceContext):
    def __init__(
        self,
        repository: CompanyOnboardingRepository,
        token_issuer: InvitationTokenIssuer,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._token_issuer = token_issuer
        self._unit_of_work = unit_of_work

    def execute(self, token: str) -> InvitationAcceptanceContext:
        if not token:
            raise InvitationNotFoundError()
        token_hash = self._token_issuer.hash(token)
        with self._unit_of_work.transaction():
            return self._repository.get_invitation_acceptance_context(
                token_hash,
                datetime.now(timezone.utc),
            )
