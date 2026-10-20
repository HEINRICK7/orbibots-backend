from collections.abc import Callable

import punq
from sqlalchemy.orm import Session

from app.src.application.usecases.authenticate_user import AuthenticateUserUseCase
from app.src.application.usecases.login import LoginUseCase
from app.src.domain.interfaces.adapters.authentication import (
    AccessTokenProvider,
    PasswordVerifier,
)
from app.src.domain.interfaces.gateways.authentication import UserAuthenticationRepository
from app.src.domain.interfaces.usecases.authentication import (
    AuthenticateUser,
    Login,
)
from app.src.infra.adapters.authentication.repository import (
    SqlAlchemyUserAuthenticationRepository,
)


RepositoryFactory = Callable[[Session], UserAuthenticationRepository]


class AuthenticationUseCaseProvider:
    """Compose request-scoped authentication use cases through Punq."""

    def __init__(
        self,
        application_container: punq.Container,
        repository_factory: RepositoryFactory = SqlAlchemyUserAuthenticationRepository,
    ) -> None:
        self._application_container = application_container
        self._repository_factory = repository_factory

    def login(self, session: Session) -> Login:
        request_container = self._container_for(session)
        return request_container.resolve(LoginUseCase)

    def authenticate_user(self, session: Session) -> AuthenticateUser:
        request_container = self._container_for(session)
        return request_container.resolve(AuthenticateUserUseCase)

    def _container_for(self, session: Session) -> punq.Container:
        request_container = punq.Container()
        request_container.register(LoginUseCase)
        request_container.register(AuthenticateUserUseCase)
        request_container.register(
            UserAuthenticationRepository,
            instance=self._repository_factory(session),
        )
        request_container.register(
            PasswordVerifier,
            instance=self._application_container.resolve(PasswordVerifier),
        )
        request_container.register(
            AccessTokenProvider,
            instance=self._application_container.resolve(AccessTokenProvider),
        )
        return request_container
