from datetime import datetime, timedelta, timezone
import unittest
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.company_onboarding.status import (
    AuditOutcome,
    CompanyStatus,
    InvitationStatus,
)
from app.src.infra.adapters.company_onboarding_repository import (
    SqlAlchemyCompanyOnboardingRepository,
)
from app.src.infra.adapters.persistence.company_onboarding_models import (
    AuditEvent,
    Company,
    Invitation,
)
from app.src.infra.setup import model_registry
from app.src.infra.adapters.persistence.transaction import SqlAlchemyUnitOfWork


class FailingAuditRepository(SqlAlchemyCompanyOnboardingRepository):
    def create_audit_event(self, actor_user_id, company_id, action, outcome):
        super().create_audit_event(actor_user_id, company_id, action, outcome)
        raise RuntimeError("audit write failed")


class SqlAlchemyCompanyOnboardingRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        model_registry.Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.repository = SqlAlchemyCompanyOnboardingRepository(self.session)

    def tearDown(self) -> None:
        self.session.close()
        model_registry.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_persists_company_invitation_and_audit_using_enum_values(self) -> None:
        now = datetime.now(timezone.utc)
        actor_id = UUID("00000000-0000-0000-0000-000000000010")
        with self.session.begin():
            company_id = self.repository.create_company(
                "Acme", CompanyStatus.PENDING_ACTIVATION, now
            )
            invitation_id = self.repository.create_invitation(
                company_id=company_id,
                invited_name="Ana",
                email="ana@example.com",
                phone=None,
                intended_role=CompanyRole.COMPANY_ADMIN,
                token_hash="a" * 64,
                status=InvitationStatus.PENDING,
                expires_at=now + timedelta(hours=24),
                created_at=now,
            )
            self.repository.create_audit_event(
                actor_id, company_id, "company.provision", AuditOutcome.SUCCESS
            )

        company = self.session.get(Company, company_id)
        invitation = self.session.get(Invitation, invitation_id)
        audit = self.session.scalar(select(AuditEvent))
        self.assertEqual(CompanyStatus.PENDING_ACTIVATION.value, company.status)
        self.assertEqual(CompanyRole.COMPANY_ADMIN.value, invitation.intended_role)
        self.assertEqual(InvitationStatus.PENDING.value, invitation.status)
        self.assertEqual("a" * 64, invitation.token_hash)
        self.assertEqual(AuditOutcome.SUCCESS.value, audit.outcome)

    def test_unit_of_work_rolls_back_company_and_invitation_if_audit_fails(self) -> None:
        from app.src.application.usecases.provision_company import (
            ProvisionCompanyUseCase,
        )
        from app.src.domain.dtos.company_onboarding import (
            CompanyInvitationRequest,
            IssuedInvitationToken,
        )
        from app.src.domain.entities.access.errors import AccessDeniedError
        from app.src.domain.entities.authentication.global_role import GlobalRole
        from app.src.domain.entities.authentication.user import AuthenticatedUser

        class TokenIssuer:
            def issue(self):
                return IssuedInvitationToken("never-stored-token", "hash")

        class AllowGlobalAdmin:
            def execute(self, user):
                if user.global_role is not GlobalRole.ADMIN:
                    raise AccessDeniedError("Global ADMIN role required.")

        actor = AuthenticatedUser(
            id=UUID("00000000-0000-0000-0000-000000000010"),
            name="Root",
            email="root@example.com",
            is_active=True,
            global_role=GlobalRole.ADMIN,
        )
        use_case = ProvisionCompanyUseCase(
            repository=FailingAuditRepository(self.session),
            token_issuer=TokenIssuer(),
            require_global_admin=AllowGlobalAdmin(),
            unit_of_work=SqlAlchemyUnitOfWork(self.session),
        )

        with self.assertRaisesRegex(RuntimeError, "audit write failed"):
            use_case.execute(
                actor,
                CompanyInvitationRequest("Acme", "Ana", "ana@example.com"),
            )

        self.assertEqual(0, len(self.session.scalars(select(Company)).all()))
        self.assertEqual(0, len(self.session.scalars(select(Invitation)).all()))


if __name__ == "__main__":
    unittest.main()
