from sqlalchemy.orm import Session

from app.src.application.usecases.grant_global_admin import GrantGlobalAdminUseCase
from app.src.domain.entities.authentication.policies import GlobalAdminAllowlist
from app.src.infra.adapters.authentication.password_hashing import (
    PasswordHashFactory,
    PwdlibPasswordHasher,
)
from app.src.infra.adapters.authentication.repository import (
    SqlAlchemyUserAuthenticationRepository,
)
from app.src.infra.setup.bootstrap_admin import BootstrapAdmin


def build_bootstrap_admin(
    session: Session,
    allowed_admin_emails: tuple[str, ...],
) -> BootstrapAdmin:
    allowlist = GlobalAdminAllowlist(allowed_admin_emails)
    repository = SqlAlchemyUserAuthenticationRepository(session)
    return BootstrapAdmin(
        session=session,
        allowlist=allowlist,
        password_hasher=PwdlibPasswordHasher(PasswordHashFactory().create()),
        grant_global_admin=GrantGlobalAdminUseCase(repository, allowlist),
    )
