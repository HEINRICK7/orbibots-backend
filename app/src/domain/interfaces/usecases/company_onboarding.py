from app.src.domain.dtos.company_onboarding import (
    AcceptedInvitationSession,
    CompanyInvitationRequest,
    EmailDispatchResult,
    InvitationAcceptanceContext,
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
    def execute(self, token: str) -> AcceptedInvitationSession: ...


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


class GetInvitationAcceptanceContext:
    def execute(self, token: str) -> InvitationAcceptanceContext: ...


class SendInvitationEmail:
    def execute(self, outbox_id: UUID, raw_token: str | None = None) -> EmailDispatchResult: ...

    def dispatch_pending(self, limit: int = 50) -> int: ...
