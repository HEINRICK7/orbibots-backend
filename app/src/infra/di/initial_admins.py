from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.src.application.usecases.grant_global_admin import GrantGlobalAdminUseCase
from app.src.application.usecases.provision_initial_admins import (
    ProvisionInitialAdminsUseCase,
)
from app.src.domain.entities.authentication.policies import GlobalAdminAllowlist
from app.src.domain.interfaces.usecases.initial_admins import (
    ProvisionInitialAdmins,
)
from app.src.infra.adapters.authentication.initial_admins import (
    SqlAlchemyInitialAdminProvisioningGateway,
)
from app.src.infra.adapters.authentication.password_hashing import PwdlibPasswordHasher
from app.src.infra.adapters.authentication.repository import (
    SqlAlchemyUserAuthenticationRepository,
)
from app.src.infra.adapters.persistence.transaction import SqlAlchemyUnitOfWork


def build_initial_admin_provisioning_use_case(
    session: Session,
    password_hash: PasswordHash,
    allowed_admin_emails: tuple[str, ...],
) -> ProvisionInitialAdmins:
    allowlist = GlobalAdminAllowlist(allowed_admin_emails)
    authentication_repository = SqlAlchemyUserAuthenticationRepository(session)
    return ProvisionInitialAdminsUseCase(
        gateway=SqlAlchemyInitialAdminProvisioningGateway(session),
        password_hasher=PwdlibPasswordHasher(password_hash),
        allowlist=allowlist,
        grant_global_admin=GrantGlobalAdminUseCase(
            authentication_repository,
            allowlist,
        ),
        unit_of_work=SqlAlchemyUnitOfWork(session),
    )
