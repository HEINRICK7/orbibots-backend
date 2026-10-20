from datetime import datetime, timezone

from app.src.application.gateways.transactions import UnitOfWork
from app.src.domain.dtos.company_onboarding import (
    AcceptedInvitation,
    AcceptedInvitationSession,
)
from app.src.domain.entities.company_onboarding.errors import InvitationNotFoundError
from app.src.domain.interfaces.adapters.authentication import AccessTokenProvider
from app.src.domain.interfaces.adapters.company_onboarding import InvitationTokenIssuer
from app.src.domain.interfaces.gateways.company_onboarding import (
    CompanyOnboardingRepository,
)
from app.src.domain.interfaces.usecases.company_onboarding import AcceptInvitation


class AcceptInvitationUseCase(AcceptInvitation):
    def __init__(
        self,
        repository: CompanyOnboardingRepository,
        token_issuer: InvitationTokenIssuer,
        access_tokens: AccessTokenProvider,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._token_issuer = token_issuer
        self._access_tokens = access_tokens
        self._unit_of_work = unit_of_work

    def execute(
        self,
        token: str,
    ) -> AcceptedInvitationSession:
        if not token:
            raise InvitationNotFoundError()

        token_hash = self._token_issuer.hash(token)
        now = datetime.now(timezone.utc)
        with self._unit_of_work.transaction():
            accepted: AcceptedInvitation = self._repository.accept_invitation(
                token_hash, now
            )
            access_token = self._access_tokens.issue(accepted.user_id)
            return AcceptedInvitationSession(
                invitation_id=accepted.invitation_id,
                company_id=accepted.company_id,
                company_name=accepted.company_name,
                user_id=accepted.user_id,
                access_token=access_token.encoded,
                expires_in=access_token.expires_in,
            )
