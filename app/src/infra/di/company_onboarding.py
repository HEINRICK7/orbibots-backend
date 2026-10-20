from sqlalchemy.orm import Session

from app.src.application.usecases.send_invitation_email import (
    SendInvitationEmailUseCase,
)
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
