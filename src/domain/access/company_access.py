from dataclasses import dataclass
from uuid import UUID

from src.domain.access.company_role import CompanyRole
from src.domain.company_onboarding.membership_scope import MembershipScope


@dataclass(frozen=True)
class CompanyAccess:
    company_id: UUID
    company_name: str
    role: CompanyRole
    scope: MembershipScope | None
