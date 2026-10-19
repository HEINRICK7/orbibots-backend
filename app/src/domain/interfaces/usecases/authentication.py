from typing import Protocol
from uuid import UUID

from app.src.domain.dtos.authentication import IssuedAccessToken
from app.src.domain.entities.authentication.user import AuthenticatedUser


class Login(Protocol):
    def execute(self, email: str, password: str) -> IssuedAccessToken: ...


class AuthenticateUser(Protocol):
    def execute(self, token: str) -> AuthenticatedUser: ...


class GrantGlobalAdmin(Protocol):
    def execute(self, email: str) -> AuthenticatedUser: ...


class RequireGlobalAdmin(Protocol):
    def execute(self, user: AuthenticatedUser) -> None: ...


class RequireCompanyAdmin(Protocol):
    def execute(self, user: AuthenticatedUser, company_id: UUID) -> None: ...
