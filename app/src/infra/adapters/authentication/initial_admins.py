from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.src.domain.dtos.initial_admins import (
    ProvisioningCompany,
    ProvisioningMembership,
    ProvisioningUser,
)
from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.authentication.status import UserStatus
from app.src.domain.entities.company_onboarding.status import (
    CompanyStatus,
    MembershipStatus,
)
from app.src.domain.interfaces.gateways.initial_admins import (
    InitialAdminProvisioningGateway,
)
from app.src.infra.adapters.persistence.authentication_models import UserRecord
from app.src.infra.adapters.persistence.company_onboarding_models import Company, Membership


class SqlAlchemyInitialAdminProvisioningGateway(InitialAdminProvisioningGateway):
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_companies_by_name(self, name: str) -> tuple[ProvisioningCompany, ...]:
        companies = self._session.scalars(
            select(Company).where(func.lower(Company.name) == name.casefold())
        ).all()
        return tuple(
            ProvisioningCompany(
                id=company.id,
                name=company.name,
                status=CompanyStatus(company.status),
            )
            for company in companies
        )

    def create_company(
        self,
        name: str,
        activated_at: datetime,
    ) -> ProvisioningCompany:
        company = Company(
            name=name,
            status=CompanyStatus.ACTIVE.value,
            activated_at=activated_at,
        )
        self._session.add(company)
        self._session.flush()
        return ProvisioningCompany(
            id=company.id,
            name=company.name,
            status=CompanyStatus(company.status),
        )

    def find_user_by_email(self, email: str) -> ProvisioningUser | None:
        user = self._session.scalar(
            select(UserRecord).where(func.lower(UserRecord.email) == email.casefold())
        )
        if user is None:
            return None
        return ProvisioningUser(
            id=user.id,
            email=user.email,
            status=UserStatus(user.status),
            has_password=user.password_hash is not None,
        )

    def create_user(
        self,
        name: str,
        email: str,
        password_hash: str,
    ) -> ProvisioningUser:
        user = UserRecord(
            name=name,
            email=email,
            password_hash=password_hash,
            status=UserStatus.ACTIVE.value,
        )
        self._session.add(user)
        self._session.flush()
        return ProvisioningUser(
            id=user.id,
            email=user.email,
            status=UserStatus(user.status),
            has_password=user.password_hash is not None,
        )

    def find_active_membership(
        self,
        company_id: UUID,
        user_id: UUID,
    ) -> ProvisioningMembership | None:
        membership = self._session.scalar(
            select(Membership).where(
                Membership.company_id == company_id,
                Membership.user_id == user_id,
                Membership.status == MembershipStatus.ACTIVE.value,
            )
        )
        if membership is None:
            return None
        return ProvisioningMembership(role=CompanyRole(membership.role))

    def create_company_membership(
        self,
        company_id: UUID,
        user_id: UUID,
        role: CompanyRole,
    ) -> None:
        self._session.add(
            Membership(
                company_id=company_id,
                user_id=user_id,
                role=role.value,
                status=MembershipStatus.ACTIVE.value,
            )
        )
