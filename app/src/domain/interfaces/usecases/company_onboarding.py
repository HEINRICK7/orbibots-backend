from app.src.domain.dtos.company_onboarding import (
    AcceptedInvitation,
    CompanyInvitationRequest,
    ProvisionCompanyResult,
)
from app.src.domain.entities.authentication.user import AuthenticatedUser


class ProvisionCompany:
    def execute(
        self, actor: AuthenticatedUser, request: CompanyInvitationRequest
    ) -> ProvisionCompanyResult: ...


class AcceptInvitation:
    def execute(
        self, token: str, password: str | None = None
    ) -> AcceptedInvitation: ...
