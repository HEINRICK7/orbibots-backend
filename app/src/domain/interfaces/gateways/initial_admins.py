from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.src.domain.dtos.initial_admins import (
    ProvisioningCompany,
    ProvisioningMembership,
    ProvisioningUser,
)
from app.src.domain.entities.access.company_role import CompanyRole


class InitialAdminProvisioningGateway(Protocol):
    def find_companies_by_name(self, name: str) -> tuple[ProvisioningCompany, ...]: ...

    def create_company(
        self, name: str, activated_at: datetime
    ) -> ProvisioningCompany: ...

    def find_user_by_email(self, email: str) -> ProvisioningUser | None: ...

    def create_user(
        self, name: str, email: str, password_hash: str
    ) -> ProvisioningUser: ...

    def find_active_membership(
        self, company_id: UUID, user_id: UUID
    ) -> ProvisioningMembership | None: ...

    def create_company_membership(
        self, company_id: UUID, user_id: UUID, role: CompanyRole
    ) -> None: ...
