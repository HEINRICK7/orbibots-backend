from app.src.domain.dtos.company_onboarding import (
    CompanyInvitationRequest,
    ProvisionCompanyResult,
)
from app.src.domain.entities.authentication.user import AuthenticatedUser


class ProvisionCompany:
    def execute(
        self, actor: AuthenticatedUser, request: CompanyInvitationRequest
    ) -> ProvisionCompanyResult: ...
