import os

from pwdlib import PasswordHash
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.src.application.usecases.provision_initial_admins import (
    InitialAdminProvisioningError,
)
from app.src.domain.dtos.initial_admins import InitialAdminAccount
from app.src.infra.adapters.authentication.password_hashing import PasswordHashFactory
from app.src.infra.di.initial_admins import (
    build_initial_admin_provisioning_use_case,
)
from app.src.infra.exceptions.errors import ConfigurationError
from app.src.infra.setup.logging_config import configure_logging
from app.src.infra.setup.settings import Settings


class InitialAdminProvisioner:
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
        self._allowed_admin_emails = allowed_admin_emails

    @classmethod
    def run_from_environment(cls) -> None:
        configure_logging()
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
        try:
            with self._session_factory() as session:
                provisioner = build_initial_admin_provisioning_use_case(
                    session,
                    password_hash,
                    self._allowed_admin_emails,
                )
                provisioner.execute(self._company_name, self._admins)
        except InitialAdminProvisioningError as exc:
            raise ConfigurationError(str(exc)) from exc

        print(
            f"Initial company admins are ready for '{self._company_name}': "
            f"{self._admins[0].email}, {self._admins[1].email}"
        )


if __name__ == "__main__":
    InitialAdminProvisioner.run_from_environment()
