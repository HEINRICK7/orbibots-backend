from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.application.authentication.use_cases.grant_global_admin import (
    GlobalAdminAllowlist,
    GrantGlobalAdminUseCase,
)
from src.infrastructure.authentication.models import UserRecord
from src.infrastructure.authentication.password_hashing import PasswordHashFactory
from src.infrastructure.authentication.repository import (
    SqlAlchemyUserAuthenticationRepository,
)


class BootstrapAdmin:
    def ensure(
        self,
        session: Session,
        *,
        email: str,
        password: str,
        name: str,
        allowed_admin_emails: tuple[str, ...],
    ) -> None:
        allowlist = GlobalAdminAllowlist(allowed_admin_emails)
        normalized_email = allowlist.ensure_allowed(email)
        existing = session.scalar(
            select(UserRecord).where(func.lower(UserRecord.email) == normalized_email)
        )
        if existing is None:
            session.add(
                UserRecord(
                    name=name.strip() or "Administrador",
                    email=normalized_email,
                    password_hash=PasswordHashFactory().create().hash(password),
                    status="ACTIVE",
                )
            )
            session.flush()

        GrantGlobalAdminUseCase(
            SqlAlchemyUserAuthenticationRepository(session),
            allowlist,
        ).execute(normalized_email)
        session.commit()
