from uuid import UUID

from app.contexts.authentication.application.ports import (
    AccessTokenProvider,
    UserAuthenticationRepository,
)
from app.contexts.authentication.domain.errors import AuthenticationError
from app.contexts.authentication.domain.user import AuthenticatedUser


class AuthenticateUserUseCase:
    def __init__(
        self,
        repository: UserAuthenticationRepository,
        access_tokens: AccessTokenProvider,
    ) -> None:
        self._repository = repository
        self._access_tokens = access_tokens

    def execute(self, token: str) -> AuthenticatedUser:
        try:
            user_id: UUID = self._access_tokens.decode_subject(token)
        except ValueError as exc:
            raise AuthenticationError from exc
        user = self._repository.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError
        return user
