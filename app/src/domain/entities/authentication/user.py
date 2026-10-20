from dataclasses import dataclass
from uuid import UUID

from app.src.domain.entities.access.company_access import CompanyAccess
from app.src.domain.entities.authentication.global_role import GlobalRole


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    name: str
    email: str
    is_active: bool
    global_role: GlobalRole | None = None
    company_accesses: tuple[CompanyAccess, ...] = ()
