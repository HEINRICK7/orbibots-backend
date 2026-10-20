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
    OutboxStatus,
)
from app.src.domain.entities.company_onboarding.errors import InvitationNotFoundError
from app.src.domain.entities.company_onboarding.errors import (
    InvitationRateLimitError,
    InvitationStateError,
)
from app.src.domain.entities.authentication.status import UserStatus
from app.src.infra.adapters.company_onboarding_repository import (
    SqlAlchemyCompanyOnboardingRepository,
)
from app.src.infra.adapters.persistence.company_onboarding_models import (
    AuditEvent,
    Company,
    Invitation,
    InvitationEmailOutbox,
    Membership,
)
from app.src.infra.adapters.persistence.authentication_models import UserRecord
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
            outbox_id = self.repository.create_invitation_outbox_event(
                invitation_id, now
            )

        company = self.session.get(Company, company_id)
        invitation = self.session.get(Invitation, invitation_id)
        audit = self.session.scalar(select(AuditEvent))
        outbox = self.session.get(InvitationEmailOutbox, outbox_id)
        self.assertEqual(CompanyStatus.PENDING_ACTIVATION.value, company.status)
        self.assertEqual(CompanyRole.COMPANY_ADMIN.value, invitation.intended_role)
        self.assertEqual(InvitationStatus.PENDING.value, invitation.status)
        self.assertEqual("a" * 64, invitation.token_hash)
        self.assertEqual(AuditOutcome.SUCCESS.value, audit.outcome)
        self.assertEqual(OutboxStatus.PENDING.value, outbox.status)

    def test_claim_and_completion_are_idempotent(self) -> None:
        now = datetime.now(timezone.utc)
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
                token_hash="b" * 64,
                status=InvitationStatus.PENDING,
                expires_at=now + timedelta(hours=24),
                created_at=now,
            )
            outbox_id = self.repository.create_invitation_outbox_event(
                invitation_id, now
            )

        with self.session.begin():
            job = self.repository.claim_invitation_email(
                outbox_id, now, now - timedelta(minutes=5)
            )
        self.assertIsNotNone(job)
        self.assertEqual(OutboxStatus.PROCESSING, job.status)
        self.assertEqual(1, job.attempts)

        with self.session.begin():
            self.repository.mark_invitation_email_sent(outbox_id, now)
        with self.session.begin():
            duplicate = self.repository.claim_invitation_email(
                outbox_id, now, now - timedelta(minutes=5)
            )

        self.assertIsNone(duplicate)
        self.assertEqual(
            OutboxStatus.SENT.value,
            self.session.get(InvitationEmailOutbox, outbox_id).status,
        )

    def test_acceptance_creates_user_membership_and_activates_company(self) -> None:
        now = datetime.now(timezone.utc)
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
                token_hash="c" * 64,
                status=InvitationStatus.PENDING,
                expires_at=now + timedelta(hours=24),
                created_at=now,
            )

        with self.session.begin():
            context = self.repository.get_invitation_acceptance_context("c" * 64, now)
            accepted = self.repository.accept_invitation("c" * 64, now, "hash-value")

        company = self.session.get(Company, company_id)
        invitation = self.session.get(Invitation, invitation_id)
        user = self.session.get(UserRecord, accepted.user_id)
        membership = self.session.scalar(select(Membership))
        audit = self.session.scalar(
            select(AuditEvent).where(AuditEvent.action == "invitation.accept")
        )
        self.assertTrue(context.requires_password_setup)
        self.assertEqual(CompanyStatus.ACTIVE.value, company.status)
        self.assertIsNotNone(company.activated_at)
        self.assertEqual(InvitationStatus.ACCEPTED.value, invitation.status)
        self.assertEqual("hash-value", user.password_hash)
        self.assertEqual(UserStatus.ACTIVE.value, user.status)
        self.assertEqual(accepted.user_id, membership.user_id)
        self.assertEqual(CompanyRole.COMPANY_ADMIN.value, membership.role)
        self.assertEqual("COMPANY", membership.scope.value)
        self.assertEqual("invitation.accept", audit.action)

        with self.assertRaises(InvitationNotFoundError):
            self.repository.get_invitation_acceptance_context("c" * 64, now)
        self.session.rollback()

    def test_accepting_for_existing_user_does_not_change_password(self) -> None:
        now = datetime.now(timezone.utc)
        existing_user_id = UUID("00000000-0000-0000-0000-000000000011")
        with self.session.begin():
            company_id = self.repository.create_company(
                "Acme", CompanyStatus.PENDING_ACTIVATION, now
            )
            self.session.add(
                UserRecord(
                    id=existing_user_id,
                    name="Ana",
                    email="ana@example.com",
                    password_hash="existing-password-hash",
                    status=UserStatus.ACTIVE,
                )
            )
            invitation_id = self.repository.create_invitation(
                company_id=company_id,
                invited_name="Ana Silva",
                email="ANA@example.com",
                phone=None,
                intended_role=CompanyRole.COMPANY_ADMIN,
                token_hash="d" * 64,
                status=InvitationStatus.PENDING,
                expires_at=now + timedelta(hours=24),
                created_at=now,
            )

        with self.session.begin():
            context = self.repository.get_invitation_acceptance_context("d" * 64, now)
            accepted = self.repository.accept_invitation("d" * 64, now, None)

        user = self.session.get(UserRecord, existing_user_id)
        invitation = self.session.get(Invitation, invitation_id)
        self.assertFalse(context.requires_password_setup)
        self.assertEqual(existing_user_id, accepted.user_id)
        self.assertEqual("existing-password-hash", user.password_hash)
        self.assertEqual(InvitationStatus.ACCEPTED.value, invitation.status)

    def test_resend_rotates_token_and_reuses_company_and_invitation(self) -> None:
        now = datetime.now(timezone.utc)
        company_id = UUID("00000000-0000-0000-0000-000000000020")
        invitation_id = UUID("00000000-0000-0000-0000-000000000021")
        with self.session.begin():
            self.session.add(Company(id=company_id, name="Acme", status=CompanyStatus.ACTIVE))
            self.session.add(
                Invitation(
                    id=invitation_id,
                    company_id=company_id,
                    invited_name="Ana",
                    email="ana@example.com",
                    intended_role=CompanyRole.COMPANY_ADMIN,
                    token_hash="old-hash",
                    status=InvitationStatus.EXPIRED,
                    expires_at=now - timedelta(hours=1),
                    created_at=now - timedelta(hours=1),
                )
            )
            old_outbox_id = self.repository.create_invitation_outbox_event(
                invitation_id, now - timedelta(minutes=2)
            )

        with self.session.begin():
            resent = self.repository.prepare_invitation_resend(
                invitation_id,
                now,
                "new-hash",
                now + timedelta(hours=24),
                timedelta(minutes=1),
            )

        invitation = self.session.get(Invitation, invitation_id)
        old_outbox = self.session.get(InvitationEmailOutbox, old_outbox_id)
        self.assertEqual(company_id, resent.company_id)
        self.assertEqual(invitation_id, resent.invitation_id)
        self.assertNotEqual(old_outbox_id, resent.outbox_id)
        self.assertEqual(InvitationStatus.PENDING.value, invitation.status)
        self.assertEqual("new-hash", invitation.token_hash)
        self.assertEqual(OutboxStatus.FAILED.value, old_outbox.status)
        self.assertEqual(1, len(self.session.scalars(select(Company)).all()))
        self.assertEqual(1, len(self.session.scalars(select(Invitation)).all()))

    def test_recent_invitation_email_enforces_resend_rate_limit(self) -> None:
        now = datetime.now(timezone.utc)
        company_id = UUID("00000000-0000-0000-0000-000000000022")
        invitation_id = UUID("00000000-0000-0000-0000-000000000023")
        with self.session.begin():
            self.session.add(Company(id=company_id, name="Acme", status=CompanyStatus.ACTIVE))
            self.session.add(
                Invitation(
                    id=invitation_id,
                    company_id=company_id,
                    invited_name="Ana",
                    email="ana@example.com",
                    intended_role=CompanyRole.COMPANY_ADMIN,
                    token_hash="old-hash",
                    status=InvitationStatus.PENDING,
                    expires_at=now + timedelta(hours=24),
                    created_at=now,
                )
            )
            self.repository.create_invitation_outbox_event(
                invitation_id, now - timedelta(seconds=10)
            )

        with self.assertRaises(InvitationRateLimitError):
            self.repository.prepare_invitation_resend(
                invitation_id,
                now,
                "new-hash",
                now + timedelta(hours=24),
                timedelta(minutes=1),
            )
        self.session.rollback()

        invitation = self.session.get(Invitation, invitation_id)
        self.assertEqual("old-hash", invitation.token_hash)

    def test_revoke_invalidates_pending_email_and_accepted_invitation_is_immutable(self) -> None:
        now = datetime.now(timezone.utc)
        company_id = UUID("00000000-0000-0000-0000-000000000024")
        invitation_id = UUID("00000000-0000-0000-0000-000000000025")
        with self.session.begin():
            self.session.add(Company(id=company_id, name="Acme", status=CompanyStatus.ACTIVE))
            self.session.add(
                Invitation(
                    id=invitation_id,
                    company_id=company_id,
                    invited_name="Ana",
                    email="ana@example.com",
                    intended_role=CompanyRole.COMPANY_ADMIN,
                    token_hash="revoke-hash",
                    status=InvitationStatus.PENDING,
                    expires_at=now + timedelta(hours=24),
                    created_at=now,
                )
            )
            outbox_id = self.repository.create_invitation_outbox_event(invitation_id, now)

        with self.session.begin():
            self.repository.revoke_invitation(invitation_id, now)

        invitation = self.session.get(Invitation, invitation_id)
        outbox = self.session.get(InvitationEmailOutbox, outbox_id)
        self.assertEqual(InvitationStatus.REVOKED.value, invitation.status)
        self.assertEqual(OutboxStatus.FAILED.value, outbox.status)
        self.session.commit()

        with self.session.begin():
            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_at = now
        with self.assertRaises(InvitationStateError):
            self.repository.revoke_invitation(invitation_id, now)
        self.session.rollback()

    def test_invitation_status_query_does_not_return_token_hash(self) -> None:
        now = datetime.now(timezone.utc)
        company_id = UUID("00000000-0000-0000-0000-000000000026")
        invitation_id = UUID("00000000-0000-0000-0000-000000000027")
        with self.session.begin():
            self.session.add(Company(id=company_id, name="Acme", status=CompanyStatus.ACTIVE))
            self.session.add(
                Invitation(
                    id=invitation_id,
                    company_id=company_id,
                    invited_name="Ana",
                    email="ana@example.com",
                    intended_role=CompanyRole.COMPANY_ADMIN,
                    token_hash="secret-hash",
                    status=InvitationStatus.PENDING,
                    expires_at=now + timedelta(hours=24),
                    created_at=now,
                )
            )

        summaries = self.repository.list_company_invitations(company_id)

        self.assertEqual(1, len(summaries))
        self.assertEqual(InvitationStatus.PENDING, summaries[0].status)
        self.assertEqual("Acme", summaries[0].company_name)
        self.assertNotIn("secret-hash", repr(summaries[0]))
        self.session.rollback()

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
        self.assertEqual(0, len(self.session.scalars(select(InvitationEmailOutbox)).all()))


if __name__ == "__main__":
    unittest.main()
