import punq
from fastapi import Request
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from src.application.authentication.use_cases.authenticate_user import (
    AuthenticateUserUseCase,
)
from src.application.authentication.use_cases.login import LoginUseCase
from src.infrastructure.authentication.password_hashing import (
    PwdlibPasswordVerifier,
)
from src.infrastructure.authentication.repository import (
    SqlAlchemyUserAuthenticationRepository,
)
from src.infrastructure.authentication.tokens import JwtAccessTokenProvider


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
