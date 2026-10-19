from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.application.authentication.use_cases.authenticate_user import (
    AuthenticateUserUseCase,
)
from src.application.authentication.use_cases.login import LoginUseCase
from src.domain.authentication.errors import AuthenticationError
from src.domain.authentication.user import AuthenticatedUser
from src.presentation.api.authentication.dependencies import (
    AuthenticateUserUseCaseProvider,
    CurrentUserDependency,
    DatabaseSession,
    RequireCompanyAdminDependency,
    RequireGlobalAdminDependency,
    database_session_dependency,
)
from src.presentation.api.authentication.schemas import (
    LoginRequest,
    LoginResponse,
    UserResponse,
)


LoginUseCaseProvider = Callable[[Request, DatabaseSession], LoginUseCase]


class AuthenticationRouter:
    _bearer_scheme = HTTPBearer(auto_error=False)

    def __init__(
        self,
        login_use_case_provider: LoginUseCaseProvider,
        authenticate_user_use_case_provider: AuthenticateUserUseCaseProvider,
    ) -> None:
        self._login_use_case_provider = login_use_case_provider
        self._authenticate_user_use_case_provider = (
            authenticate_user_use_case_provider
        )
        self.require_global_admin = RequireGlobalAdminDependency(
            CurrentUserDependency(authenticate_user_use_case_provider)
        )
        self.require_company_admin = RequireCompanyAdminDependency(
            CurrentUserDependency(authenticate_user_use_case_provider)
        )
        self.router = APIRouter()
        self.router.add_api_route(
            "/login",
            self.login,
            methods=["POST"],
            response_model=LoginResponse,
        )
        self.router.add_api_route(
            "/me",
            self.get_authenticated_user,
            methods=["GET"],
            response_model=UserResponse,
        )

    def login(
        self,
        payload: LoginRequest,
        request: Request,
        session: DatabaseSession = Depends(database_session_dependency),
    ) -> LoginResponse:
        use_case = self._login_use_case_provider(request, session)
        try:
            token = use_case.execute(payload.email, payload.password)
        except AuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            ) from exc
        return LoginResponse(
            access_token=token.encoded,
            token_type="bearer",
            expires_in=token.expires_in,
        )

    def get_authenticated_user(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
        session: DatabaseSession = Depends(database_session_dependency),
    ) -> UserResponse:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        use_case = self._authenticate_user_use_case_provider(request, session)
        try:
            user: AuthenticatedUser = use_case.execute(credentials.credentials)
        except AuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        return UserResponse.model_validate(user)
