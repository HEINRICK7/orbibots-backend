from dataclasses import dataclass, field
from uuid import UUID

from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.authentication.status import UserStatus
from app.src.domain.entities.company_onboarding.status import CompanyStatus


@dataclass(frozen=True)
class InitialAdminAccount:
    name: str
    email: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class ProvisioningCompany:
    id: UUID
    name: str
    status: CompanyStatus


@dataclass(frozen=True)
class ProvisioningUser:
    id: UUID
    email: str
    status: UserStatus
    has_password: bool


@dataclass(frozen=True)
class ProvisioningMembership:
    role: CompanyRole
