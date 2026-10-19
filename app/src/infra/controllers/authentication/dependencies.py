from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from typing import Any
from uuid import UUID

from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.interfaces.usecases.authentication import (
    AuthenticateUser,
    RequireCompanyAdmin,
    RequireGlobalAdmin,
)
from app.src.infra.exceptions.errors import (
    AuthenticationRequiredError,
    DatabaseUnavailableError,
)


DatabaseSession = Any
SessionFactory = Callable[[], AbstractContextManager[DatabaseSession]]
AuthenticateUserUseCaseProvider = Callable[[DatabaseSession], AuthenticateUser]


class DatabaseSessionDependency:
    def __call__(self, request: Request) -> Iterator[DatabaseSession]:
        session_factory: SessionFactory | None = request.app.state.session_factory
        if session_factory is None:
            raise DatabaseUnavailableError
        with session_factory() as session:
            yield session


database_session_dependency = DatabaseSessionDependency()


class CurrentUserDependency:
    _bearer_scheme = HTTPBearer(auto_error=False)

    def __init__(
        self,
        authenticate_user_use_case_provider: AuthenticateUserUseCaseProvider,
    ) -> None:
        self._authenticate_user_use_case_provider = authenticate_user_use_case_provider

    def __call__(
        self,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
        session: DatabaseSession = Depends(database_session_dependency),
    ) -> AuthenticatedUser:
        return self.resolve(credentials, session)

    def resolve(
        self,
        credentials: HTTPAuthorizationCredentials | None,
        session: DatabaseSession,
    ) -> AuthenticatedUser:
        if credentials is None:
            raise AuthenticationRequiredError

        use_case = self._authenticate_user_use_case_provider(session)
        return use_case.execute(credentials.credentials)


class RequireGlobalAdminDependency:
    def __init__(
        self,
        current_user_dependency: CurrentUserDependency,
        authorize: RequireGlobalAdmin,
    ) -> None:
        self._current_user_dependency = current_user_dependency
        self._authorize = authorize

    def __call__(
        self,
        credentials: HTTPAuthorizationCredentials | None = Depends(
            CurrentUserDependency._bearer_scheme
        ),
        session: DatabaseSession = Depends(database_session_dependency),
    ) -> AuthenticatedUser:
        user = self._current_user_dependency.resolve(credentials, session)
        self._authorize.execute(user)
        return user


class RequireCompanyAdminDependency:
    def __init__(
        self,
        current_user_dependency: CurrentUserDependency,
        authorize: RequireCompanyAdmin,
    ) -> None:
        self._current_user_dependency = current_user_dependency
        self._authorize = authorize

    def __call__(
        self,
        company_id: UUID = Path(...),
        credentials: HTTPAuthorizationCredentials | None = Depends(
            CurrentUserDependency._bearer_scheme
        ),
        session: DatabaseSession = Depends(database_session_dependency),
    ) -> AuthenticatedUser:
        user = self._current_user_dependency.resolve(credentials, session)
        self._authorize.execute(user, company_id)
        return user
