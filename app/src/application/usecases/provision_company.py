import re
from datetime import datetime, timedelta, timezone

from app.src.application.gateways.transactions import UnitOfWork
from app.src.domain.dtos.company_onboarding import (
    CompanyInvitationRequest,
    ProvisionCompanyResult,
)
from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.entities.company_onboarding.errors import (
    InvalidCompanyOnboardingInputError,
)
from app.src.domain.entities.company_onboarding.status import (
    AuditOutcome,
    CompanyStatus,
    InvitationStatus,
)
from app.src.domain.interfaces.adapters.company_onboarding import InvitationTokenIssuer
from app.src.domain.interfaces.gateways.company_onboarding import (
    CompanyOnboardingRepository,
)
from app.src.domain.interfaces.usecases.authentication import RequireGlobalAdmin
from app.src.domain.interfaces.usecases.company_onboarding import ProvisionCompany


class ProvisionCompanyUseCase(ProvisionCompany):
    invitation_lifetime = timedelta(hours=24)
    _email_pattern = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+\Z")

    def __init__(
        self,
        repository: CompanyOnboardingRepository,
        token_issuer: InvitationTokenIssuer,
        require_global_admin: RequireGlobalAdmin,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._token_issuer = token_issuer
        self._require_global_admin = require_global_admin
        self._unit_of_work = unit_of_work

    def execute(
        self,
        actor: AuthenticatedUser,
        request: CompanyInvitationRequest,
    ) -> ProvisionCompanyResult:
        self._require_global_admin.execute(actor)
        company_name, admin_name, email, phone = self._validate(request)
        now = datetime.now(timezone.utc)
        expires_at = now + self.invitation_lifetime
        issued_token = self._token_issuer.issue()

        with self._unit_of_work.transaction():
            company_id = self._repository.create_company(
                company_name,
                CompanyStatus.PENDING_ACTIVATION,
                now,
            )
            invitation_id = self._repository.create_invitation(
                company_id=company_id,
                invited_name=admin_name,
                email=email,
                phone=phone,
                intended_role=CompanyRole.COMPANY_ADMIN,
                token_hash=issued_token.token_hash,
                status=InvitationStatus.PENDING,
                expires_at=expires_at,
                created_at=now,
            )
            self._repository.create_audit_event(
                actor.id,
                company_id,
                "company.provision",
                AuditOutcome.SUCCESS,
            )

        return ProvisionCompanyResult(
            company_id=company_id,
            invitation_id=invitation_id,
            company_name=company_name,
            admin_name=admin_name,
            email=email,
            expires_at=expires_at,
            raw_token=issued_token.raw_token,
        )

    @classmethod
    def _validate(
        cls, request: CompanyInvitationRequest
    ) -> tuple[str, str, str, str | None]:
        company_name = request.company_name.strip()
        admin_name = request.admin_name.strip()
        email = request.email.strip().casefold()
        phone = request.phone.strip() if request.phone and request.phone.strip() else None

        if not company_name or len(company_name) > 255:
            raise InvalidCompanyOnboardingInputError(
                "Company name must contain 1 to 255 characters."
            )
        if not admin_name or len(admin_name) > 255:
            raise InvalidCompanyOnboardingInputError(
                "Administrator name must contain 1 to 255 characters."
            )
        if len(email) > 320 or not cls._email_pattern.fullmatch(email):
            raise InvalidCompanyOnboardingInputError("A valid email address is required.")
        if phone is not None and len(phone) > 32:
            raise InvalidCompanyOnboardingInputError(
                "Phone must contain 32 characters or fewer."
            )
        return company_name, admin_name, email, phone
