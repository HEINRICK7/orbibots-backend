from uuid import UUID

from src.domain.access.errors import AccessDeniedError
from src.domain.access.policy import AccessPolicy
from src.domain.authentication.user import AuthenticatedUser


class RequireGlobalAdminUseCase:
    def execute(self, user: AuthenticatedUser) -> None:
        if not AccessPolicy.can_access_global_admin_area(user):
            raise AccessDeniedError("Global ADMIN role required.")


class RequireCompanyAdminUseCase:
    def execute(self, user: AuthenticatedUser, company_id: UUID) -> None:
        if not AccessPolicy.can_access_company_area(user, company_id):
            raise AccessDeniedError(
                "Active COMPANY_ADMIN membership for this company required."
            )
