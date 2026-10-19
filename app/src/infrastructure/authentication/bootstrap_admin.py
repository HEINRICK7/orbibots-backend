from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.src.infrastructure.authentication.models import UserRecord
from app.src.infrastructure.authentication.password_hashing import PasswordHashFactory


class BootstrapAdmin:
    def ensure(self, session: Session, *, email: str, password: str, name: str) -> None:
        normalized_email = email.strip().lower()
        existing = session.scalar(
            select(UserRecord).where(func.lower(UserRecord.email) == normalized_email)
        )
        if existing is not None:
            return
        session.add(
            UserRecord(
                name=name.strip() or "Administrador",
                email=normalized_email,
                password_hash=PasswordHashFactory().create().hash(password),
                status="ACTIVE",
            )
        )
        session.commit()
