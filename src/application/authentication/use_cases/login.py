from src.application.authentication.ports import (
    AccessTokenProvider,
    IssuedAccessToken,
    PasswordVerifier,
    UserAuthenticationRepository,
)
from src.domain.authentication.errors import AuthenticationError


class LoginUseCase:
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
            raise AuthenticationError
        if not self._password_verifier.verify(password, credentials.password_hash):
            raise AuthenticationError
        return self._access_tokens.issue(credentials.user.id)
