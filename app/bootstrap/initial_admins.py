import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pwdlib import PasswordHash
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.contexts.authentication.application.use_cases.grant_global_admin import (
    GlobalAdminAllowlist,
    GrantGlobalAdminUseCase,
)
from app.contexts.authentication.infrastructure.models import UserRecord
from app.contexts.authentication.infrastructure.password_hashing import (
    PasswordHashFactory,
)
from app.contexts.authentication.infrastructure.repository import (
    SqlAlchemyUserAuthenticationRepository,
)
from app.contexts.company_onboarding.infrastructure.models import Company, Membership
from app.platform.config import ConfigurationError, Settings


@dataclass(frozen=True)
class InitialAdminAccount:
    name: str
    email: str
    password: str = field(repr=False)


class InitialAdminProvisioner:
    minimum_password_length = 20

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        company_name: str,
        admins: tuple[InitialAdminAccount, InitialAdminAccount],
        allowed_admin_emails: tuple[str, ...],
    ) -> None:
        self._session_factory = session_factory
        self._company_name = company_name.strip()
        self._admins = admins
        self._allowlist = GlobalAdminAllowlist(allowed_admin_emails)

    @classmethod
    def run_from_environment(cls) -> None:
        settings = Settings.from_environment()
        if not settings.database_url:
            raise ConfigurationError(
                "DATABASE_URL is required to provision initial admins."
            )

        company_name = os.getenv("INITIAL_COMPANY_NAME", "").strip()
        admins = (
            InitialAdminAccount(
                name=os.getenv("INITIAL_ADMIN_1_NAME", "").strip(),
                email=os.getenv("INITIAL_ADMIN_1_EMAIL", "").strip(),
                password=os.getenv("INITIAL_ADMIN_1_PASSWORD", ""),
            ),
            InitialAdminAccount(
                name=os.getenv("INITIAL_ADMIN_2_NAME", "").strip(),
                email=os.getenv("INITIAL_ADMIN_2_EMAIL", "").strip(),
                password=os.getenv("INITIAL_ADMIN_2_PASSWORD", ""),
            ),
        )
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        try:
            provisioner = cls(
                sessionmaker(
                    bind=engine,
                    autoflush=False,
                    expire_on_commit=False,
                ),
                company_name,
                admins,
                settings.global_admin_allowed_emails,
            )
            provisioner.execute(PasswordHashFactory().create())
        finally:
            engine.dispose()

    def execute(self, password_hash: PasswordHash) -> None:
        self._validate_configuration()
        with self._session_factory() as session, session.begin():
            company = self._get_or_create_company(session)
            grant_global_admin = GrantGlobalAdminUseCase(
                SqlAlchemyUserAuthenticationRepository(session),
                self._allowlist,
            )
            for admin in self._admins:
                user = self._get_or_create_user(session, admin, password_hash)
                self._ensure_admin_membership(session, company, user)
                grant_global_admin.execute(user.email)

        print(
            f"Initial company admins are ready for '{self._company_name}': "
            f"{self._admins[0].email}, {self._admins[1].email}"
        )

    def _validate_configuration(self) -> None:
        if not self._company_name:
            raise ConfigurationError("INITIAL_COMPANY_NAME must not be empty.")
        if len(self._company_name) > 255:
            raise ConfigurationError("INITIAL_COMPANY_NAME must be 255 characters or fewer.")

        emails = [admin.email.casefold() for admin in self._admins]
        if len(set(emails)) != len(emails):
            raise ConfigurationError("Initial admin email addresses must be unique.")
        if not self._allowlist.matches(admin.email for admin in self._admins):
            raise ConfigurationError(
                "Initial admin identities must exactly match GLOBAL_ADMIN_ALLOWED_EMAILS."
            )

        for index, admin in enumerate(self._admins, start=1):
            if not admin.name or len(admin.name) > 255:
                raise ConfigurationError(
                    f"INITIAL_ADMIN_{index}_NAME must contain 1 to 255 characters."
                )
            if not admin.email or len(admin.email) > 320 or "@" not in admin.email:
                raise ConfigurationError(
                    f"INITIAL_ADMIN_{index}_EMAIL must be a valid email address."
                )
            if len(admin.password) < self.minimum_password_length:
                raise ConfigurationError(
                    f"INITIAL_ADMIN_{index}_PASSWORD must contain at least "
                    f"{self.minimum_password_length} characters."
                )
        if self._admins[0].password == self._admins[1].password:
            raise ConfigurationError("Initial admin passwords must be different.")

    def _get_or_create_company(self, session: Session) -> Company:
        companies = session.scalars(
            select(Company).where(func.lower(Company.name) == self._company_name.casefold())
        ).all()
        if len(companies) > 1:
            raise ConfigurationError(
                f"Multiple companies match '{self._company_name}'. Resolve duplicates first."
            )
        if companies:
            company = companies[0]
            if company.status != "ACTIVE":
                raise ConfigurationError(
                    f"Company '{self._company_name}' exists but is not ACTIVE."
                )
            return company

        company = Company(
            name=self._company_name,
            status="ACTIVE",
            activated_at=datetime.now(timezone.utc),
        )
        session.add(company)
        session.flush()
        return company

    def _get_or_create_user(
        self,
        session: Session,
        admin: InitialAdminAccount,
        password_hash: PasswordHash,
    ) -> UserRecord:
        user = session.scalar(
            select(UserRecord).where(func.lower(UserRecord.email) == admin.email.casefold())
        )
        if user is not None:
            if user.status != "ACTIVE":
                raise ConfigurationError(
                    f"Existing user '{admin.email}' is not ACTIVE."
                )
            if user.password_hash is None:
                raise ConfigurationError(
                    f"Existing user '{admin.email}' has no password hash. "
                    "Set a password through the approved account-recovery flow."
                )
            return user

        user = UserRecord(
            name=admin.name,
            email=admin.email,
            password_hash=password_hash.hash(admin.password),
            status="ACTIVE",
        )
        session.add(user)
        session.flush()
        return user

    def _ensure_admin_membership(
        self,
        session: Session,
        company: Company,
        user: UserRecord,
    ) -> None:
        membership = session.scalar(
            select(Membership).where(
                Membership.company_id == company.id,
                Membership.user_id == user.id,
                Membership.status == "ACTIVE",
            )
        )
        if membership is not None:
            if membership.role != "COMPANY_ADMIN":
                raise ConfigurationError(
                    f"User '{user.email}' already has a different active role "
                    f"for '{company.name}'."
                )
            return

        session.add(
            Membership(
                company_id=company.id,
                user_id=user.id,
                role="COMPANY_ADMIN",
                status="ACTIVE",
            )
        )


if __name__ == "__main__":
    InitialAdminProvisioner.run_from_environment()
