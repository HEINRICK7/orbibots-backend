from uuid import UUID

from app.src.domain.entities.access.errors import AccessDeniedError
from app.src.domain.entities.access.policy import AccessPolicy
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.interfaces.usecases.authentication import (
    RequireCompanyAdmin,
    RequireGlobalAdmin,
)


class RequireGlobalAdminUseCase(RequireGlobalAdmin):
    def execute(self, user: AuthenticatedUser) -> None:
        if not AccessPolicy.can_access_global_admin_area(user):
            raise AccessDeniedError("Global ADMIN role required.")


class RequireCompanyAdminUseCase(RequireCompanyAdmin):
    def execute(self, user: AuthenticatedUser, company_id: UUID) -> None:
        if not AccessPolicy.can_access_company_area(user, company_id):
            raise AccessDeniedError(
                "Active COMPANY_ADMIN membership for this company required."
            )
