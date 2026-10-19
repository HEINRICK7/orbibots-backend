from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.application.access.authorize_access import (
    RequireCompanyAdminUseCase,
    RequireGlobalAdminUseCase,
)
from src.application.authentication.use_cases.authenticate_user import (
    AuthenticateUserUseCase,
)
from src.domain.access.errors import AccessDeniedError
from src.domain.authentication.errors import AuthenticationError
from src.domain.authentication.user import AuthenticatedUser


DatabaseSession = Any
SessionFactory = Callable[[], AbstractContextManager[DatabaseSession]]
AuthenticateUserUseCaseProvider = Callable[
    [Request, DatabaseSession], AuthenticateUserUseCase
]


class DatabaseSessionDependency:
    def __call__(self, request: Request) -> Iterator[DatabaseSession]:
        session_factory: SessionFactory | None = (
            request.app.state.session_factory
        )
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is not configured.",
            )
        with session_factory() as session:
            yield session


database_session_dependency = DatabaseSessionDependency()


class CurrentUserDependency:
    _bearer_scheme = HTTPBearer(auto_error=False)

    def __init__(
        self,
        authenticate_user_use_case_provider: AuthenticateUserUseCaseProvider,
    ) -> None:
        self._authenticate_user_use_case_provider = (
            authenticate_user_use_case_provider
        )

    def __call__(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
        session: DatabaseSession = Depends(database_session_dependency),
    ) -> AuthenticatedUser:
        return self.resolve(request, credentials, session)

    def resolve(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials | None,
        session: DatabaseSession,
    ) -> AuthenticatedUser:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        use_case = self._authenticate_user_use_case_provider(request, session)
        try:
            user = use_case.execute(credentials.credentials)
        except AuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        return user


class RequireGlobalAdminDependency:
    def __init__(self, current_user_dependency: CurrentUserDependency) -> None:
        self._current_user_dependency = current_user_dependency
        self._authorize = RequireGlobalAdminUseCase()

    def __call__(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(
            CurrentUserDependency._bearer_scheme
        ),
        session: DatabaseSession = Depends(database_session_dependency),
    ) -> AuthenticatedUser:
        user = self._current_user_dependency.resolve(request, credentials, session)
        try:
            self._authorize.execute(user)
        except AccessDeniedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        return user


class RequireCompanyAdminDependency:
    def __init__(self, current_user_dependency: CurrentUserDependency) -> None:
        self._current_user_dependency = current_user_dependency
        self._authorize = RequireCompanyAdminUseCase()

    def __call__(
        self,
        request: Request,
        company_id: UUID = Path(...),
        credentials: HTTPAuthorizationCredentials | None = Depends(
            CurrentUserDependency._bearer_scheme
        ),
        session: DatabaseSession = Depends(database_session_dependency),
    ) -> AuthenticatedUser:
        user = self._current_user_dependency.resolve(request, credentials, session)
        try:
            self._authorize.execute(user, company_id)
        except AccessDeniedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        return user

