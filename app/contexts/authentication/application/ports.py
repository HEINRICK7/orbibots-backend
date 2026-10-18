from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.contexts.authentication.domain.user import AuthenticatedUser


@dataclass(frozen=True)
class UserCredentials:
    user: AuthenticatedUser
    password_hash: str | None


@dataclass(frozen=True)
class IssuedAccessToken:
    encoded: str
    expires_in: int


class UserAuthenticationRepository(Protocol):
    def get_credentials_by_email(self, email: str) -> UserCredentials | None: ...

    def get_by_id(self, user_id: UUID) -> AuthenticatedUser | None: ...


class PasswordVerifier(Protocol):
    def verify(self, password: str, encoded_hash: str) -> bool: ...


class AccessTokenProvider(Protocol):
    def issue(self, user_id: UUID) -> IssuedAccessToken: ...

    def decode_subject(self, token: str) -> UUID: ...
