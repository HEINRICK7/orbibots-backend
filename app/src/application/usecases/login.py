from app.src.domain.dtos.authentication import IssuedAccessToken
from app.src.domain.entities.authentication.errors import InvalidCredentialsError
from app.src.domain.interfaces.adapters.authentication import (
    AccessTokenProvider,
    PasswordVerifier,
)
from app.src.domain.interfaces.gateways.authentication import UserAuthenticationRepository
from app.src.domain.interfaces.usecases.authentication import Login


class LoginUseCase(Login):
    def __init__(
        self,
        repository: UserAuthenticationRepository,
        password_verifier: PasswordVerifier,
        access_tokens: AccessTokenProvider,
    ) -> None:
        self._repository = repository
        self._password_verifier = password_verifier
        self._access_tokens = access_tokens

    def execute(self, email: str, password: str) -> IssuedAccessToken:
        credentials = self._repository.get_credentials_by_email(email)
        if (
            credentials is None
            or not credentials.user.is_active
            or credentials.password_hash is None
        ):
            raise InvalidCredentialsError
        if not self._password_verifier.verify(password, credentials.password_hash):
            raise InvalidCredentialsError
        return self._access_tokens.issue(credentials.user.id)
