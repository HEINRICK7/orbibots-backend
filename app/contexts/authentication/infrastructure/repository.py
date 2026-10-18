from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contexts.authentication.application.ports import UserCredentials
from app.contexts.authentication.domain.user import AuthenticatedUser
from app.contexts.authentication.infrastructure.models import UserRecord


class SqlAlchemyUserAuthenticationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_credentials_by_email(self, email: str) -> UserCredentials | None:
        normalized_email = email.strip().lower()
        user = self._session.scalar(
            select(UserRecord).where(func.lower(UserRecord.email) == normalized_email)
        )
        if user is None:
            return None
        return UserCredentials(
            user=self._to_domain(user),
            password_hash=user.password_hash,
        )

    def get_by_id(self, user_id: UUID) -> AuthenticatedUser | None:
        user = self._session.get(UserRecord, user_id)
        return self._to_domain(user) if user is not None else None

    @staticmethod
    def _to_domain(user: UserRecord) -> AuthenticatedUser:
        return AuthenticatedUser(
            id=user.id,
            name=user.name,
            email=user.email,
            is_active=user.status == "ACTIVE",
        )
