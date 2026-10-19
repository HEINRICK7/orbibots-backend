from typing import Protocol
from uuid import UUID

from app.src.domain.dtos.authentication import (
    GlobalAdminGrantCandidate,
    UserCredentials,
)
from app.src.domain.entities.authentication.user import AuthenticatedUser


class UserAuthenticationRepository(Protocol):
    def get_credentials_by_email(self, email: str) -> UserCredentials | None: ...

    def get_by_id(self, user_id: UUID) -> AuthenticatedUser | None: ...


class GlobalAdminGrantRepository(Protocol):
    def get_global_admin_grant_candidate(
        self, email: str
    ) -> GlobalAdminGrantCandidate | None: ...

    def grant_global_admin(self, email: str) -> AuthenticatedUser | None: ...
