from datetime import datetime, timezone
from uuid import UUID

from app.src.application.gateways.transactions import UnitOfWork
from app.src.domain.dtos.initial_admins import (
    InitialAdminAccount,
    ProvisioningCompany,
    ProvisioningUser,
)
from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.authentication.policies import GlobalAdminAllowlist
from app.src.domain.entities.authentication.status import UserStatus
from app.src.domain.entities.company_onboarding.status import CompanyStatus
from app.src.domain.interfaces.adapters.authentication import PasswordHasher
from app.src.domain.interfaces.gateways.initial_admins import (
    InitialAdminProvisioningGateway,
)
from app.src.domain.interfaces.usecases.initial_admins import (
    ProvisionInitialAdmins,
)
from app.src.domain.interfaces.usecases.authentication import GrantGlobalAdmin


class InitialAdminProvisioningError(ValueError):
    """The initial company administrator configuration cannot be provisioned."""


class ProvisionInitialAdminsUseCase(ProvisionInitialAdmins):
    minimum_password_length = 20

    def __init__(
        self,
        gateway: InitialAdminProvisioningGateway,
        password_hasher: PasswordHasher,
        allowlist: GlobalAdminAllowlist,
        grant_global_admin: GrantGlobalAdmin,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._gateway = gateway
        self._password_hasher = password_hasher
        self._allowlist = allowlist
        self._grant_global_admin = grant_global_admin
        self._unit_of_work = unit_of_work

    def execute(
        self,
        company_name: str,
        admins: tuple[InitialAdminAccount, InitialAdminAccount],
    ) -> None:
        normalized_company_name = company_name.strip()
        self._validate_configuration(normalized_company_name, admins)
        with self._unit_of_work.transaction():
            self._provision(normalized_company_name, admins)

    def _provision(
        self,
        company_name: str,
        admins: tuple[InitialAdminAccount, InitialAdminAccount],
    ) -> None:
        company = self._get_or_create_company(company_name)

        for admin in admins:
            user = self._get_or_create_user(admin)
            self._ensure_admin_membership(company.id, user.id, user.email, company.name)
            self._grant_global_admin.execute(user.email)

    def _validate_configuration(
        self,
        company_name: str,
        admins: tuple[InitialAdminAccount, InitialAdminAccount],
    ) -> None:
        if not company_name:
            raise InitialAdminProvisioningError(
                "INITIAL_COMPANY_NAME must not be empty."
            )
        if len(company_name) > 255:
            raise InitialAdminProvisioningError(
                "INITIAL_COMPANY_NAME must be 255 characters or fewer."
            )

        emails = [admin.email.casefold() for admin in admins]
        if len(set(emails)) != len(emails):
            raise InitialAdminProvisioningError(
                "Initial admin email addresses must be unique."
            )
        if not self._allowlist.matches(admin.email for admin in admins):
            raise InitialAdminProvisioningError(
                "Initial admin identities must exactly match GLOBAL_ADMIN_ALLOWED_EMAILS."
            )

        for index, admin in enumerate(admins, start=1):
            if not admin.name or len(admin.name) > 255:
                raise InitialAdminProvisioningError(
                    f"INITIAL_ADMIN_{index}_NAME must contain 1 to 255 characters."
                )
            if not admin.email or len(admin.email) > 320 or "@" not in admin.email:
                raise InitialAdminProvisioningError(
                    f"INITIAL_ADMIN_{index}_EMAIL must be a valid email address."
                )
            if len(admin.password) < self.minimum_password_length:
                raise InitialAdminProvisioningError(
                    f"INITIAL_ADMIN_{index}_PASSWORD must contain at least "
                    f"{self.minimum_password_length} characters."
                )
        if admins[0].password == admins[1].password:
            raise InitialAdminProvisioningError(
                "Initial admin passwords must be different."
            )

    def _get_or_create_company(self, company_name: str) -> ProvisioningCompany:
        companies = self._gateway.find_companies_by_name(company_name)
        if len(companies) > 1:
            raise InitialAdminProvisioningError(
                f"Multiple companies match '{company_name}'. Resolve duplicates first."
            )
        if companies:
            company = companies[0]
            if company.status is not CompanyStatus.ACTIVE:
                raise InitialAdminProvisioningError(
                    f"Company '{company_name}' exists but is not ACTIVE."
                )
            return company

        return self._gateway.create_company(
            company_name,
            datetime.now(timezone.utc),
        )

    def _get_or_create_user(self, admin: InitialAdminAccount) -> ProvisioningUser:
        user = self._gateway.find_user_by_email(admin.email)
        if user is not None:
            if user.status is not UserStatus.ACTIVE:
                raise InitialAdminProvisioningError(
                    f"Existing user '{admin.email}' is not ACTIVE."
                )
            if not user.has_password:
                raise InitialAdminProvisioningError(
                    f"Existing user '{admin.email}' has no password hash. "
                    "Set a password through the approved account-recovery flow."
                )
            return user

        password_hash = self._password_hasher.hash(admin.password)
        return self._gateway.create_user(admin.name, admin.email, password_hash)

    def _ensure_admin_membership(
        self,
        company_id: UUID,
        user_id: UUID,
        email: str,
        company_name: str,
    ) -> None:
        membership = self._gateway.find_active_membership(company_id, user_id)
        if membership is not None:
            if membership.role is not CompanyRole.COMPANY_ADMIN:
                raise InitialAdminProvisioningError(
                    f"User '{email}' already has a different active role "
                    f"for '{company_name}'."
                )
            return

        self._gateway.create_company_membership(
            company_id,
            user_id,
            CompanyRole.COMPANY_ADMIN,
        )
