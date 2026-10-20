from dataclasses import dataclass
from uuid import UUID

from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.company_onboarding.membership_scope import MembershipScope


@dataclass(frozen=True)
class CompanyAccess:
    company_id: UUID
    company_name: str
    role: CompanyRole
    scope: MembershipScope | None
