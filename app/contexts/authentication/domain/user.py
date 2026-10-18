from dataclasses import dataclass
from uuid import UUID

from app.contexts.authentication.domain.global_role import GlobalRole


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    name: str
    email: str
    is_active: bool
    global_role: GlobalRole | None = None
