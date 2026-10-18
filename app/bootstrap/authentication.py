import punq
from fastapi import Request
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.contexts.authentication.application.use_cases.authenticate_user import (
    AuthenticateUserUseCase,
)
from app.contexts.authentication.application.use_cases.login import LoginUseCase
from app.contexts.authentication.infrastructure.password_hashing import (
    PwdlibPasswordVerifier,
)
from app.contexts.authentication.infrastructure.repository import (
    SqlAlchemyUserAuthenticationRepository,
)
from app.contexts.authentication.infrastructure.tokens import JwtAccessTokenProvider


class AuthenticationUseCaseProvider:
    def login(self, request: Request, session: Session) -> LoginUseCase:
        container: punq.Container = request.app.state.container
        return LoginUseCase(
            repository=SqlAlchemyUserAuthenticationRepository(session),
            password_verifier=PwdlibPasswordVerifier(
                container.resolve(PasswordHash)
            ),
            access_tokens=container.resolve(JwtAccessTokenProvider),
        )

    def authenticate_user(
        self,
        request: Request,
        session: Session,
    ) -> AuthenticateUserUseCase:
        container: punq.Container = request.app.state.container
        return AuthenticateUserUseCase(
            repository=SqlAlchemyUserAuthenticationRepository(session),
            access_tokens=container.resolve(JwtAccessTokenProvider),
        )
