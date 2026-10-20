from collections.abc import Callable

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.interfaces.usecases.authentication import (
    Login,
    RequireCompanyAdmin,
    RequireGlobalAdmin,
)
from app.src.infra.controllers.authentication.dependencies import (
    AuthenticateUserUseCaseProvider,
    CurrentUserDependency,
    DatabaseSession,
    RequireCompanyAdminDependency,
    RequireGlobalAdminDependency,
    database_session_dependency,
)
from app.src.infra.controllers.authentication.schemas import (
    LoginRequest,
    LoginResponse,
    UserResponse,
)


LoginUseCaseProvider = Callable[[DatabaseSession], Login]


class AuthenticationRouter:
    _bearer_scheme = HTTPBearer(auto_error=False)

    def __init__(
        self,
        login_use_case_provider: LoginUseCaseProvider,
        authenticate_user_use_case_provider: AuthenticateUserUseCaseProvider,
        require_global_admin: RequireGlobalAdmin,
        require_company_admin: RequireCompanyAdmin,
    ) -> None:
        self._login_use_case_provider = login_use_case_provider
        self._current_user_dependency = CurrentUserDependency(
            authenticate_user_use_case_provider
        )
        self.require_global_admin = RequireGlobalAdminDependency(
            self._current_user_dependency,
            require_global_admin,
        )
        self.require_company_admin = RequireCompanyAdminDependency(
            self._current_user_dependency,
            require_company_admin,
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
        session: DatabaseSession = Depends(database_session_dependency),
    ) -> LoginResponse:
        token = self._login_use_case_provider(session).execute(
            payload.email,
            payload.password,
        )
        return LoginResponse(
            access_token=token.encoded,
            token_type="bearer",
            expires_in=token.expires_in,
        )

    def get_authenticated_user(
        self,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
        session: DatabaseSession = Depends(database_session_dependency),
    ) -> UserResponse:
        user: AuthenticatedUser = self._current_user_dependency.resolve(
            credentials,
            session,
        )
        return UserResponse.model_validate(user)
