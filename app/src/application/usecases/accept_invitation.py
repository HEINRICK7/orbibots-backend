from datetime import datetime, timezone

from app.src.application.gateways.transactions import UnitOfWork
from app.src.domain.dtos.company_onboarding import AcceptedInvitation
from app.src.domain.entities.company_onboarding.errors import (
    InvalidCompanyOnboardingInputError,
    InvitationNotFoundError,
)
from app.src.domain.interfaces.adapters.authentication import PasswordHasher
from app.src.domain.interfaces.adapters.company_onboarding import InvitationTokenIssuer
from app.src.domain.interfaces.gateways.company_onboarding import (
    CompanyOnboardingRepository,
)
from app.src.domain.interfaces.usecases.company_onboarding import AcceptInvitation


class AcceptInvitationUseCase(AcceptInvitation):
    minimum_password_length = 12

    def __init__(
        self,
        repository: CompanyOnboardingRepository,
        token_issuer: InvitationTokenIssuer,
        password_hasher: PasswordHasher,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._token_issuer = token_issuer
        self._password_hasher = password_hasher
        self._unit_of_work = unit_of_work

    def execute(
        self,
        token: str,
        password: str | None = None,
    ) -> AcceptedInvitation:
        if not token:
            raise InvitationNotFoundError()

        token_hash = self._token_issuer.hash(token)
        now = datetime.now(timezone.utc)
        with self._unit_of_work.transaction():
            context = self._repository.get_invitation_acceptance_context(
                token_hash,
                now,
            )
            password_hash = self._password_hash_for(context.requires_password_setup, password)
            return self._repository.accept_invitation(token_hash, now, password_hash)

    def _password_hash_for(self, required: bool, password: str | None) -> str | None:
        if not required:
            if password is not None:
                raise InvalidCompanyOnboardingInputError(
                    "Password must be changed through the account security flow."
                )
            return None
        if password is None or len(password) < self.minimum_password_length:
            raise InvalidCompanyOnboardingInputError(
                f"A password of at least {self.minimum_password_length} characters is required."
            )
        if len(password) > 1024:
            raise InvalidCompanyOnboardingInputError(
                "Password must contain 1024 characters or fewer."
            )
        return self._password_hasher.hash(password)
