from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.src.domain.entities.authentication.policies import GlobalAdminAllowlist
from app.src.domain.entities.authentication.status import UserStatus
from app.src.domain.interfaces.adapters.authentication import PasswordHasher
from app.src.domain.interfaces.usecases.authentication import GrantGlobalAdmin
from app.src.infra.adapters.persistence.authentication_models import UserRecord


class BootstrapAdmin:
    def __init__(
        self,
        session: Session,
        allowlist: GlobalAdminAllowlist,
        password_hasher: PasswordHasher,
        grant_global_admin: GrantGlobalAdmin,
    ) -> None:
        self._session = session
        self._allowlist = allowlist
        self._password_hasher = password_hasher
        self._grant_global_admin = grant_global_admin

    def ensure(
        self,
        *,
        email: str,
        password: str,
        name: str,
    ) -> None:
        normalized_email = self._allowlist.ensure_allowed(email)
        existing = self._session.scalar(
            select(UserRecord).where(func.lower(UserRecord.email) == normalized_email)
        )
        if existing is None:
            self._session.add(
                UserRecord(
                    name=name.strip() or "Administrador",
                    email=normalized_email,
                    password_hash=self._password_hasher.hash(password),
                    status=UserStatus.ACTIVE.value,
                )
            )
            self._session.flush()

        self._grant_global_admin.execute(normalized_email)
        self._session.commit()
