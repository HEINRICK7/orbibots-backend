from app.src.domain.dtos.company_onboarding import (
    AcceptedInvitation,
    CompanyInvitationRequest,
    InvitationSummary,
    ProvisionCompanyResult,
    ResentInvitation,
    RevokedInvitation,
)
from app.src.domain.entities.authentication.user import AuthenticatedUser
from uuid import UUID


class ProvisionCompany:
    def execute(
        self, actor: AuthenticatedUser, request: CompanyInvitationRequest
    ) -> ProvisionCompanyResult: ...


class AcceptInvitation:
    def execute(
        self, token: str, password: str | None = None
    ) -> AcceptedInvitation: ...


class ResendInvitation:
    def execute(
        self, actor: AuthenticatedUser, invitation_id: UUID
    ) -> ResentInvitation: ...


class RevokeInvitation:
    def execute(
        self, actor: AuthenticatedUser, invitation_id: UUID
    ) -> RevokedInvitation: ...


class ListCompanyInvitations:
    def execute(
        self, actor: AuthenticatedUser, company_id: UUID
    ) -> tuple[InvitationSummary, ...]: ...
