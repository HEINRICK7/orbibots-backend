from dataclasses import dataclass

from app.src.domain.entities.authentication.user import AuthenticatedUser


@dataclass(frozen=True)
class UserCredentials:
    user: AuthenticatedUser
    password_hash: str | None


@dataclass(frozen=True)
class GlobalAdminGrantCandidate:
    is_active: bool
    has_password: bool


@dataclass(frozen=True)
class IssuedAccessToken:
    encoded: str
    expires_in: int
