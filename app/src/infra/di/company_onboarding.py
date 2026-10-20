from sqlalchemy.orm import Session

from app.src.application.usecases.accept_invitation import AcceptInvitationUseCase
from app.src.application.usecases.get_invitation_acceptance_context import (
    GetInvitationAcceptanceContextUseCase,
)
from app.src.application.usecases.list_company_invitations import (
    ListCompanyInvitationsUseCase,
)
from app.src.application.usecases.list_company_onboarding import (
    ListCompanyOnboardingUseCase,
)
from app.src.application.usecases.provision_company import ProvisionCompanyUseCase
from app.src.application.usecases.resend_invitation import ResendInvitationUseCase
from app.src.application.usecases.revoke_invitation import RevokeInvitationUseCase
from app.src.application.usecases.send_invitation_email import (
    SendInvitationEmailUseCase,
)
from app.src.domain.interfaces.adapters.authentication import AccessTokenProvider
from app.src.domain.interfaces.usecases.authentication import RequireGlobalAdmin
from app.src.infra.adapters.authentication.invitation_tokens import (
    SecureInvitationTokenIssuer,
)
from app.src.infra.adapters.company_onboarding_repository import (
    SqlAlchemyCompanyOnboardingRepository,
)
from app.src.infra.adapters.email.smtp_invitation_sender import (
    SmtpInvitationEmailSender,
)
from app.src.infra.adapters.persistence.transaction import SqlAlchemyUnitOfWork
from app.src.infra.setup.settings import Settings


class CompanyOnboardingUseCaseProvider:
    def __init__(
        self,
        require_global_admin: RequireGlobalAdmin,
        access_tokens: AccessTokenProvider,
    ) -> None:
        self._require_global_admin = require_global_admin
        self._access_tokens = access_tokens

    def provision_company(self, session: Session) -> ProvisionCompanyUseCase:
        return ProvisionCompanyUseCase(
            repository=SqlAlchemyCompanyOnboardingRepository(session),
            token_issuer=SecureInvitationTokenIssuer(),
            require_global_admin=self._require_global_admin,
            unit_of_work=SqlAlchemyUnitOfWork(session),
        )

    def accept_invitation(self, session: Session) -> AcceptInvitationUseCase:
        return AcceptInvitationUseCase(
            repository=SqlAlchemyCompanyOnboardingRepository(session),
            token_issuer=SecureInvitationTokenIssuer(),
            access_tokens=self._access_tokens,
            unit_of_work=SqlAlchemyUnitOfWork(session),
        )

    def invitation_acceptance_context(
        self, session: Session
    ) -> GetInvitationAcceptanceContextUseCase:
        return GetInvitationAcceptanceContextUseCase(
            repository=SqlAlchemyCompanyOnboardingRepository(session),
            token_issuer=SecureInvitationTokenIssuer(),
            unit_of_work=SqlAlchemyUnitOfWork(session),
        )

    def resend_invitation(self, session: Session) -> ResendInvitationUseCase:
        return ResendInvitationUseCase(
            repository=SqlAlchemyCompanyOnboardingRepository(session),
            token_issuer=SecureInvitationTokenIssuer(),
            require_global_admin=self._require_global_admin,
            unit_of_work=SqlAlchemyUnitOfWork(session),
        )

    def revoke_invitation(self, session: Session) -> RevokeInvitationUseCase:
        return RevokeInvitationUseCase(
            repository=SqlAlchemyCompanyOnboardingRepository(session),
            require_global_admin=self._require_global_admin,
            unit_of_work=SqlAlchemyUnitOfWork(session),
        )

    def list_company_invitations(self, session: Session) -> ListCompanyInvitationsUseCase:
        return ListCompanyInvitationsUseCase(
            repository=SqlAlchemyCompanyOnboardingRepository(session),
            require_global_admin=self._require_global_admin,
        )

    def list_company_onboarding(self, session: Session) -> ListCompanyOnboardingUseCase:
        return ListCompanyOnboardingUseCase(
            repository=SqlAlchemyCompanyOnboardingRepository(session),
            require_global_admin=self._require_global_admin,
        )


def build_send_invitation_email_use_case(
    session: Session,
    settings: Settings,
) -> SendInvitationEmailUseCase:
    if not settings.invitation_email_configured or not settings.invitation_base_url:
        raise ValueError("Invitation email delivery is not configured.")
    return SendInvitationEmailUseCase(
        repository=SqlAlchemyCompanyOnboardingRepository(session),
        token_issuer=SecureInvitationTokenIssuer(),
        email_sender=SmtpInvitationEmailSender(settings),
        unit_of_work=SqlAlchemyUnitOfWork(session),
        invitation_base_url=settings.invitation_base_url,
    )
