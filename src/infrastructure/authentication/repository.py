from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.application.authentication.ports import UserCredentials
from src.domain.access.company_access import CompanyAccess
from src.domain.access.company_role import CompanyRole
from src.domain.authentication.errors import GlobalAdminGrantError
from src.domain.authentication.global_role import GlobalRole
from src.domain.authentication.user import AuthenticatedUser
from src.infrastructure.authentication.models import UserRecord


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
            user=self._to_domain(user, include_company_accesses=False),
            password_hash=user.password_hash,
        )

    def get_by_id(self, user_id: UUID) -> AuthenticatedUser | None:
        user = self._session.get(UserRecord, user_id)
        return self._to_domain(user) if user is not None else None

    def grant_global_admin(self, email: str) -> AuthenticatedUser:
        user = self._session.scalar(
            select(UserRecord).where(func.lower(UserRecord.email) == email)
        )
        if user is None or user.status != "ACTIVE" or user.password_hash is None:
            raise GlobalAdminGrantError(
                "Only an active user with a password hash can receive global ADMIN."
            )
        user.global_role = GlobalRole.ADMIN.value
        self._session.flush()
        return self._to_domain(user)

    @staticmethod
    def _to_domain(
        user: UserRecord,
        *,
        include_company_accesses: bool = True,
    ) -> AuthenticatedUser:
        company_accesses = ()
        if include_company_accesses:
            company_accesses = tuple(
                CompanyAccess(
                    company_id=membership.company_id,
                    company_name=membership.company.name,
                    role=CompanyRole(membership.role),
                    scope=membership.scope,
                )
                for membership in user.memberships
                if membership.status == "ACTIVE"
                and membership.company.status == "ACTIVE"
            )
        return AuthenticatedUser(
            id=user.id,
            name=user.name,
            email=user.email,
            is_active=user.status == "ACTIVE",
            global_role=GlobalRole(user.global_role) if user.global_role else None,
            company_accesses=company_accesses,
        )
