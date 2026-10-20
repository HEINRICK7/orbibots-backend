from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends

from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.entities.company_onboarding.status import (
    InvitationStatus,
    OutboxStatus,
)
from app.src.domain.interfaces.usecases.company_onboarding import (
    AcceptInvitation,
    GetInvitationAcceptanceContext,
    ListCompanyInvitations,
    ListCompanyOnboarding,
    ProvisionCompany,
    ResendInvitation,
    RevokeInvitation,
    SendInvitationEmail,
)
from app.src.infra.controllers.authentication.dependencies import (
    DatabaseSession,
    database_session_dependency,
)
from app.src.infra.controllers.company_onboarding.schemas import (
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    CompanyOnboardingSummaryResponse,
    InvitationSummaryResponse,
    InvitationValidationRequest,
    InvitationValidationResponse,
    ProvisionCompanyRequest,
    ProvisionCompanyResponse,
    ResendInvitationResponse,
    RevokeInvitationResponse,
)


ProvisionCompanyUseCaseProvider = Callable[[DatabaseSession], ProvisionCompany]
AcceptInvitationUseCaseProvider = Callable[[DatabaseSession], AcceptInvitation]
InvitationContextUseCaseProvider = Callable[[DatabaseSession], GetInvitationAcceptanceContext]
ResendInvitationUseCaseProvider = Callable[[DatabaseSession], ResendInvitation]
RevokeInvitationUseCaseProvider = Callable[[DatabaseSession], RevokeInvitation]
ListCompanyInvitationsUseCaseProvider = Callable[[DatabaseSession], ListCompanyInvitations]
ListCompanyOnboardingUseCaseProvider = Callable[[DatabaseSession], ListCompanyOnboarding]
InvitationEmailDispatcherProvider = Callable[[DatabaseSession], SendInvitationEmail]
GlobalAdminDependency = Callable[..., AuthenticatedUser]


class CompanyOnboardingRouter:
    def __init__(
        self,
        provision_company: ProvisionCompanyUseCaseProvider,
        accept_invitation: AcceptInvitationUseCaseProvider,
        invitation_acceptance_context: InvitationContextUseCaseProvider,
        resend_invitation: ResendInvitationUseCaseProvider,
        revoke_invitation: RevokeInvitationUseCaseProvider,
        list_company_invitations: ListCompanyInvitationsUseCaseProvider,
        list_company_onboarding: ListCompanyOnboardingUseCaseProvider,
        require_global_admin: GlobalAdminDependency,
        invitation_email_dispatcher: InvitationEmailDispatcherProvider | None,
    ) -> None:
        self._provision_company = provision_company
        self._accept_invitation = accept_invitation
        self._invitation_acceptance_context = invitation_acceptance_context
        self._resend_invitation = resend_invitation
        self._revoke_invitation = revoke_invitation
        self._list_company_invitations = list_company_invitations
        self._list_company_onboarding = list_company_onboarding
        self._invitation_email_dispatcher = invitation_email_dispatcher
        self.router = APIRouter()

        def provision_route(
            payload: ProvisionCompanyRequest,
            actor: AuthenticatedUser = Depends(require_global_admin),
            session: DatabaseSession = Depends(database_session_dependency),
        ) -> ProvisionCompanyResponse:
            return self._create_company(payload, actor, session)

        def list_route(
            company_id: UUID,
            actor: AuthenticatedUser = Depends(require_global_admin),
            session: DatabaseSession = Depends(database_session_dependency),
        ) -> list[InvitationSummaryResponse]:
            return self._list_invitations(company_id, actor, session)

        def list_companies_route(
            actor: AuthenticatedUser = Depends(require_global_admin),
            session: DatabaseSession = Depends(database_session_dependency),
        ) -> list[CompanyOnboardingSummaryResponse]:
            summaries = self._list_company_onboarding(session).execute(actor)
            return [
                CompanyOnboardingSummaryResponse.model_validate(item)
                for item in summaries
            ]

        def resend_route(
            invitation_id: UUID,
            actor: AuthenticatedUser = Depends(require_global_admin),
            session: DatabaseSession = Depends(database_session_dependency),
        ) -> ResendInvitationResponse:
            return self._resend(invitation_id, actor, session)

        def revoke_route(
            invitation_id: UUID,
            actor: AuthenticatedUser = Depends(require_global_admin),
            session: DatabaseSession = Depends(database_session_dependency),
        ) -> RevokeInvitationResponse:
            return self._revoke(invitation_id, actor, session)

        def validate_route(
            payload: InvitationValidationRequest,
            session: DatabaseSession = Depends(database_session_dependency),
        ) -> InvitationValidationResponse:
            return self._validate(payload, session)

        def accept_route(
            payload: AcceptInvitationRequest,
            session: DatabaseSession = Depends(database_session_dependency),
        ) -> AcceptInvitationResponse:
            return self._accept(payload, session)

        self.router.add_api_route(
            "/companies",
            list_companies_route,
            methods=["GET"],
            response_model=list[CompanyOnboardingSummaryResponse],
        )
        self.router.add_api_route(
            "/companies",
            provision_route,
            methods=["POST"],
            response_model=ProvisionCompanyResponse,
            status_code=201,
        )
        self.router.add_api_route(
            "/companies/{company_id}/invitations",
            list_route,
            methods=["GET"],
            response_model=list[InvitationSummaryResponse],
        )
        self.router.add_api_route(
            "/invitations/{invitation_id}/resend",
            resend_route,
            methods=["POST"],
            response_model=ResendInvitationResponse,
        )
        self.router.add_api_route(
            "/invitations/{invitation_id}/revoke",
            revoke_route,
            methods=["POST"],
            response_model=RevokeInvitationResponse,
        )
        self.router.add_api_route(
            "/public/invitations/validate",
            validate_route,
            methods=["POST"],
            response_model=InvitationValidationResponse,
        )
        self.router.add_api_route(
            "/public/invitations/accept",
            accept_route,
            methods=["POST"],
            response_model=AcceptInvitationResponse,
        )

    def _create_company(
        self,
        payload: ProvisionCompanyRequest,
        actor: AuthenticatedUser,
        session: DatabaseSession,
    ) -> ProvisionCompanyResponse:
        result = self._provision_company(session).execute(actor, payload.to_command())
        delivery_status = OutboxStatus.PENDING
        if self._invitation_email_dispatcher is not None:
            delivery_result = self._invitation_email_dispatcher(session).execute(
                result.outbox_id,
                raw_token=result.raw_token,
            )
            if delivery_result.sent:
                delivery_status = OutboxStatus.SENT
        return ProvisionCompanyResponse(
            company_id=result.company_id,
            invitation_id=result.invitation_id,
            invitation_status=InvitationStatus.PENDING,
            email_delivery_status=delivery_status,
            expires_at=result.expires_at,
        )

    def _list_invitations(
        self,
        company_id: UUID,
        actor: AuthenticatedUser,
        session: DatabaseSession,
    ) -> list[InvitationSummaryResponse]:
        summaries = self._list_company_invitations(session).execute(actor, company_id)
        return [InvitationSummaryResponse.model_validate(item) for item in summaries]

    def _resend(
        self,
        invitation_id: UUID,
        actor: AuthenticatedUser,
        session: DatabaseSession,
    ) -> ResendInvitationResponse:
        result = self._resend_invitation(session).execute(actor, invitation_id)
        delivery_status = OutboxStatus.PENDING
        if self._invitation_email_dispatcher is not None:
            delivery_result = self._invitation_email_dispatcher(session).execute(
                result.outbox_id,
                raw_token=result.raw_token,
            )
            if delivery_result.sent:
                delivery_status = OutboxStatus.SENT
        return ResendInvitationResponse(
            invitation_id=result.invitation_id,
            email_delivery_status=delivery_status,
            expires_at=result.expires_at,
        )

    def _revoke(
        self,
        invitation_id: UUID,
        actor: AuthenticatedUser,
        session: DatabaseSession,
    ) -> RevokeInvitationResponse:
        result = self._revoke_invitation(session).execute(actor, invitation_id)
        return RevokeInvitationResponse(
            invitation_id=result.invitation_id,
            status=InvitationStatus.REVOKED,
        )

    def _validate(
        self,
        payload: InvitationValidationRequest,
        session: DatabaseSession,
    ) -> InvitationValidationResponse:
        result = self._invitation_acceptance_context(session).execute(payload.token)
        return InvitationValidationResponse(
            company_name=result.company_name,
            invited_name=result.invited_name,
            email_masked=_mask_email(result.email),
            role=result.intended_role,
            expires_at=result.expires_at,
        )

    def _accept(
        self,
        payload: AcceptInvitationRequest,
        session: DatabaseSession,
    ) -> AcceptInvitationResponse:
        result = self._accept_invitation(session).execute(payload.token)
        return AcceptInvitationResponse(
            accepted=True,
            company_id=result.company_id,
            company_name=result.company_name,
            access_token=result.access_token,
            expires_in=result.expires_in,
        )


def _mask_email(email: str) -> str:
    local_part, separator, domain = email.partition("@")
    if not separator:
        return ""
    return f"{local_part[:1]}***@{domain}"
