from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID
import unittest

from app.src.application.usecases.provision_company import (
    ProvisionCompanyUseCase,
)
from app.src.domain.dtos.company_onboarding import CompanyInvitationRequest
from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.access.errors import AccessDeniedError
from app.src.domain.entities.authentication.global_role import GlobalRole
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.entities.company_onboarding.status import (
    AuditOutcome,
    CompanyStatus,
    InvitationStatus,
    OutboxStatus,
)
from app.src.domain.entities.company_onboarding.errors import (
    CompanyOnboardingConflictError,
    InvalidCompanyOnboardingInputError,
)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.transactions = 0

    @contextmanager
    def transaction(self):
        self.transactions += 1
        yield


class FakeRepository:
    def __init__(self) -> None:
        self.company = None
        self.invitation = None
        self.audit = []
        self.pending_invitation_email = False

    def has_pending_invitation_for_email(self, email):
        return self.pending_invitation_email

    def create_company(self, name, status, created_at):
        self.company = {
            "id": UUID("00000000-0000-0000-0000-000000000001"),
            "name": name,
            "status": status,
            "created_at": created_at,
        }
        return self.company["id"]

    def create_invitation(
        self,
        company_id,
        invited_name,
        email,
        phone,
        intended_role,
        token_hash,
        status,
        expires_at,
        created_at,
    ):
        self.invitation = {
            "id": UUID("00000000-0000-0000-0000-000000000002"),
            "company_id": company_id,
            "invited_name": invited_name,
            "email": email,
            "phone": phone,
            "intended_role": intended_role,
            "token_hash": token_hash,
            "status": status,
            "expires_at": expires_at,
            "created_at": created_at,
        }
        return self.invitation["id"]

    def create_audit_event(self, actor_user_id, company_id, action, outcome):
        self.audit.append((actor_user_id, company_id, action, outcome))

    def create_invitation_outbox_event(self, invitation_id, created_at):
        return UUID("00000000-0000-0000-0000-000000000005")


class FakeGlobalAdminAuthorizer:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, user):
        self.calls += 1
        if user.global_role is not GlobalRole.ADMIN:
            raise AccessDeniedError("Global ADMIN role required.")


class FakeTokenIssuer:
    def issue(self):
        from app.src.domain.dtos.company_onboarding import IssuedInvitationToken

        return IssuedInvitationToken(raw_token="one-time-secret", token_hash="sha256")


class ProvisionCompanyUseCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeRepository()
        self.unit_of_work = FakeUnitOfWork()
        self.authorizer = FakeGlobalAdminAuthorizer()
        self.use_case = ProvisionCompanyUseCase(
            repository=self.repository,
            token_issuer=FakeTokenIssuer(),
            require_global_admin=self.authorizer,
            unit_of_work=self.unit_of_work,
        )
        self.actor = AuthenticatedUser(
            id=UUID("00000000-0000-0000-0000-000000000003"),
            name="Root",
            email="root@example.com",
            is_active=True,
            global_role=GlobalRole.ADMIN,
        )

    def test_provisions_pending_company_and_company_admin_invitation_atomically(self) -> None:
        before = datetime.now(timezone.utc)

        result = self.use_case.execute(
            self.actor,
            CompanyInvitationRequest(
                company_name="  Acme  ",
                admin_name="  Ana Silva  ",
                email=" ANA@EXAMPLE.COM ",
                phone=" +55 85 99999-0000 ",
            ),
        )

        after = datetime.now(timezone.utc)
        self.assertEqual("Acme", self.repository.company["name"])
        self.assertEqual(CompanyStatus.PENDING_ACTIVATION, self.repository.company["status"])
        self.assertEqual("Ana Silva", self.repository.invitation["invited_name"])
        self.assertEqual("ana@example.com", self.repository.invitation["email"])
        self.assertEqual("+55 85 99999-0000", self.repository.invitation["phone"])
        self.assertEqual(CompanyRole.COMPANY_ADMIN, self.repository.invitation["intended_role"])
        self.assertEqual("sha256", self.repository.invitation["token_hash"])
        self.assertEqual(InvitationStatus.PENDING, self.repository.invitation["status"])
        self.assertGreaterEqual(self.repository.invitation["expires_at"], before + timedelta(hours=24))
        self.assertLessEqual(self.repository.invitation["expires_at"], after + timedelta(hours=24))
        self.assertEqual("one-time-secret", result.raw_token)
        self.assertEqual(
            UUID("00000000-0000-0000-0000-000000000005"), result.outbox_id
        )
        self.assertEqual(1, self.unit_of_work.transactions)
        self.assertEqual(
            [(self.actor.id, self.repository.company["id"], "company.provision", AuditOutcome.SUCCESS)],
            self.repository.audit,
        )

    def test_rejects_invalid_email_before_opening_transaction(self) -> None:
        with self.assertRaises(InvalidCompanyOnboardingInputError):
            self.use_case.execute(
                self.actor,
                CompanyInvitationRequest("Acme", "Ana", "not-an-email"),
            )

        self.assertEqual(0, self.unit_of_work.transactions)
        self.assertIsNone(self.repository.company)

    def test_rejects_an_email_with_an_existing_pending_invitation(self) -> None:
        self.repository.pending_invitation_email = True

        with self.assertRaises(CompanyOnboardingConflictError):
            self.use_case.execute(
                self.actor,
                CompanyInvitationRequest("Acme", "Ana", "ANA@example.com"),
            )

        self.assertEqual(1, self.unit_of_work.transactions)
        self.assertIsNone(self.repository.company)

    def test_rejects_blank_company_name(self) -> None:
        with self.assertRaises(InvalidCompanyOnboardingInputError):
            self.use_case.execute(
                self.actor,
                CompanyInvitationRequest("  ", "Ana", "ana@example.com"),
            )

    def test_authorization_is_checked_before_any_transaction(self) -> None:
        regular_user = AuthenticatedUser(
            id=UUID("00000000-0000-0000-0000-000000000004"),
            name="Ana",
            email="ana@example.com",
            is_active=True,
        )

        with self.assertRaises(AccessDeniedError):
            self.use_case.execute(
                regular_user,
                CompanyInvitationRequest("Acme", "Ana", "ana@example.com"),
            )
        self.assertEqual(0, self.unit_of_work.transactions)


if __name__ == "__main__":
    unittest.main()
