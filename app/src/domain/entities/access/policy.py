from uuid import UUID

from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.authentication.global_role import GlobalRole
from app.src.domain.entities.authentication.user import AuthenticatedUser


class AccessPolicy:
    @staticmethod
    def can_access_global_admin_area(user: AuthenticatedUser) -> bool:
        return user.is_active and user.global_role is GlobalRole.ADMIN

    @staticmethod
    def can_access_company_area(
        user: AuthenticatedUser,
        company_id: UUID,
    ) -> bool:
        return user.is_active and any(
            access.company_id == company_id
            and access.role is CompanyRole.COMPANY_ADMIN
            for access in user.company_accesses
        )
