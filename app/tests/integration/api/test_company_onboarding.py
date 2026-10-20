from datetime import datetime, timedelta, timezone
import unittest
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.authentication.global_role import GlobalRole
from app.src.domain.entities.authentication.status import UserStatus
from app.src.domain.entities.company_onboarding.membership_scope import MembershipScope
from app.src.domain.entities.company_onboarding.status import (
    AuditOutcome,
    CompanyStatus,
    InvitationStatus,
    MembershipStatus,
    OutboxStatus,
)
from app.src.infra.adapters.authentication.invitation_tokens import (
    SecureInvitationTokenIssuer,
)
from app.src.infra.adapters.authentication.password_hashing import PasswordHashFactory
from app.src.infra.adapters.persistence.authentication_models import UserRecord
from app.src.infra.adapters.persistence.company_onboarding_models import (
    AuditEvent,
    Company,
    Invitation,
    InvitationEmailOutbox,
    Membership,
)
from app.src.infra.entrypoints.app import create_app
from app.src.infra.setup import model_registry
from app.src.infra.setup.settings import Settings


class CompanyOnboardingApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.password_hash = PasswordHashFactory().create()
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        model_registry.Base.metadata.create_all(cls.engine)
        cls.session_factory = sessionmaker(
            bind=cls.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        cls.root_email = "root@example.com"
        cls.root_password = "root-test-password"
        cls.user_email = "member@example.com"
        cls.user_password = "member-test-password"
        with cls.session_factory() as session:
            session.add_all(
                (
                    UserRecord(
                        name="Root",
                        email=cls.root_email,
                        password_hash=cls.password_hash.hash(cls.root_password),
                        global_role=GlobalRole.ADMIN,
                        status=UserStatus.ACTIVE,
                    ),
                    UserRecord(
                        name="Member",
                        email=cls.user_email,
                        password_hash=cls.password_hash.hash(cls.user_password),
                        status=UserStatus.ACTIVE,
                    ),
                )
            )
            session.commit()
        cls.settings = Settings(
            app_env="test",
            jwt_secret_key="company-onboarding-test-secret-0123456789",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        model_registry.Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def setUp(self) -> None:
        self.client = TestClient(
            create_app(self.settings, session_factory=self.session_factory)
        )
        self.root_headers = self._login(self.root_email, self.root_password)
        self.member_headers = self._login(self.user_email, self.user_password)

    def tearDown(self) -> None:
        self.client.close()

    def test_super_admin_provisions_company_and_pending_outbox_without_returning_token(self) -> None:
        response = self.client.post(
            "/company-onboarding/companies",
            headers=self.root_headers,
            json={
                "company_name": "  Acme  ",
                "admin_name": "  Ana Silva  ",
                "email": " ANA@EXAMPLE.COM ",
                "phone": "+55 85 99999-0000",
            },
        )

        self.assertEqual(201, response.status_code)
        payload = response.json()
        self.assertNotIn("token", payload)
        self.assertNotIn("raw_token", payload)
        self.assertEqual(InvitationStatus.PENDING.value, payload["invitation_status"])
        self.assertEqual(OutboxStatus.PENDING.value, payload["email_delivery_status"])
        with self.session_factory() as session:
            company = session.get(Company, UUID(payload["company_id"]))
            invitation = session.get(Invitation, UUID(payload["invitation_id"]))
            outbox = session.scalar(
                select(InvitationEmailOutbox).where(
                    InvitationEmailOutbox.invitation_id == invitation.id
                )
            )
            audit = session.scalar(
                select(AuditEvent).where(AuditEvent.action == "company.provision")
            )
            self.assertEqual("Acme", company.name)
            self.assertEqual(CompanyStatus.PENDING_ACTIVATION.value, company.status)
            self.assertEqual("ana@example.com", invitation.email)
            self.assertEqual(InvitationStatus.PENDING.value, invitation.status)
            self.assertNotIn("one-time-token", invitation.token_hash)
            self.assertEqual(OutboxStatus.PENDING.value, outbox.status)
            self.assertEqual(AuditOutcome.SUCCESS.value, audit.outcome)

    def test_non_admin_cannot_provision_or_list_company_invitations(self) -> None:
        create_response = self.client.post(
            "/company-onboarding/companies",
            headers=self.member_headers,
            json={
                "company_name": "Unauthorized",
                "admin_name": "Member",
                "email": "other@example.com",
            },
        )
        list_response = self.client.get(
            f"/company-onboarding/companies/{uuid4()}/invitations",
            headers=self.member_headers,
        )

        self.assertEqual(403, create_response.status_code)
        self.assertEqual(403, list_response.status_code)

    def test_public_validation_and_acceptance_create_active_admin_membership_once(self) -> None:
        raw_token = "test-invitation-token"
        token_hash = SecureInvitationTokenIssuer().hash(raw_token)
        now = datetime.now(timezone.utc)
        company_id = uuid4()
        invitation_id = uuid4()
        with self.session_factory() as session:
            session.add(
                Company(
                    id=company_id,
                    name="Invite Company",
                    status=CompanyStatus.PENDING_ACTIVATION,
                )
            )
            session.flush()
            session.add(
                Invitation(
                    id=invitation_id,
                    company_id=company_id,
                    invited_name="New Admin",
                    email="new-admin@example.com",
                    intended_role=CompanyRole.COMPANY_ADMIN,
                    intended_scope=MembershipScope.COMPANY,
                    token_hash=token_hash,
                    status=InvitationStatus.PENDING,
                    expires_at=now + timedelta(hours=24),
                    created_at=now,
                )
            )
            session.commit()

        validation = self.client.post(
            "/company-onboarding/public/invitations/validate",
            json={"token": raw_token},
        )
        password_payload = self.client.post(
            "/company-onboarding/public/invitations/accept",
            json={"token": raw_token, "password": None},
        )
        acceptance = self.client.post(
            "/company-onboarding/public/invitations/accept",
            json={"token": raw_token},
        )
        replay = self.client.post(
            "/company-onboarding/public/invitations/accept",
            json={"token": raw_token},
        )
        authenticated = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {acceptance.json()['access_token']}"},
        )

        self.assertEqual(200, validation.status_code)
        self.assertNotIn("requires_password_setup", validation.json())
        self.assertNotIn("email", validation.json())
        self.assertEqual("n***@example.com", validation.json()["email_masked"])
        self.assertEqual(CompanyRole.COMPANY_ADMIN.value, validation.json()["role"])
        self.assertEqual(422, password_payload.status_code)
        self.assertEqual(200, acceptance.status_code)
        self.assertNotEqual(raw_token, acceptance.json()["access_token"])
        self.assertEqual("bearer", acceptance.json()["token_type"])
        self.assertEqual(200, authenticated.status_code)
        self.assertEqual(
            [str(company_id)],
            [
                membership["company_id"]
                for membership in authenticated.json()["company_accesses"]
            ],
        )
        self.assertEqual(409, replay.status_code)
        self.assertEqual("INVITATION_ALREADY_ACCEPTED", replay.json()["code"])
        with self.session_factory() as session:
            company = session.get(Company, company_id)
            invitation = session.get(Invitation, invitation_id)
            membership = session.scalar(
                select(Membership).where(Membership.company_id == company_id)
            )
            audit = session.scalar(
                select(AuditEvent).where(AuditEvent.action == "invitation.accept")
            )
            user = session.scalar(
                select(UserRecord).where(UserRecord.email == "new-admin@example.com")
            )
            self.assertEqual(CompanyStatus.ACTIVE.value, company.status)
            self.assertEqual(InvitationStatus.ACCEPTED.value, invitation.status)
            self.assertEqual(MembershipStatus.ACTIVE.value, membership.status)
            self.assertEqual(CompanyRole.COMPANY_ADMIN.value, membership.role)
            self.assertEqual(company_id, membership.company_id)
            self.assertEqual(AuditOutcome.SUCCESS.value, audit.outcome)
            self.assertIsNone(user.password_hash)

    def test_public_validation_distinguishes_expired_revoked_and_invalid_tokens(self) -> None:
        now = datetime.now(timezone.utc)
        company_id = uuid4()
        expired_token = "expired-invitation-token"
        revoked_token = "revoked-invitation-token"
        with self.session_factory() as session:
            session.add(Company(id=company_id, name="Invite Company", status=CompanyStatus.ACTIVE))
            session.flush()
            session.add_all(
                [
                    Invitation(
                        id=uuid4(),
                        company_id=company_id,
                        invited_name="Expired Admin",
                        email="expired@example.com",
                        intended_role=CompanyRole.COMPANY_ADMIN,
                        intended_scope=MembershipScope.COMPANY,
                        token_hash=SecureInvitationTokenIssuer().hash(expired_token),
                        status=InvitationStatus.PENDING,
                        expires_at=now - timedelta(hours=1),
                        created_at=now - timedelta(days=1),
                    ),
                    Invitation(
                        id=uuid4(),
                        company_id=company_id,
                        invited_name="Revoked Admin",
                        email="revoked@example.com",
                        intended_role=CompanyRole.COMPANY_ADMIN,
                        intended_scope=MembershipScope.COMPANY,
                        token_hash=SecureInvitationTokenIssuer().hash(revoked_token),
                        status=InvitationStatus.REVOKED,
                        expires_at=now + timedelta(hours=24),
                        created_at=now,
                        revoked_at=now,
                    ),
                ]
            )
            session.commit()

        expired = self.client.post(
            "/company-onboarding/public/invitations/validate",
            json={"token": expired_token},
        )
        revoked = self.client.post(
            "/company-onboarding/public/invitations/validate",
            json={"token": revoked_token},
        )
        invalid = self.client.post(
            "/company-onboarding/public/invitations/validate",
            json={"token": "unknown-invitation-token"},
        )

        self.assertEqual(410, expired.status_code)
        self.assertEqual("INVITATION_EXPIRED", expired.json()["code"])
        self.assertEqual(410, revoked.status_code)
        self.assertEqual("INVITATION_REVOKED", revoked.json()["code"])
        self.assertEqual(400, invalid.status_code)
        self.assertEqual("INVITATION_UNAVAILABLE", invalid.json()["code"])

    def test_admin_can_list_resend_and_revoke_without_exposing_token(self) -> None:
        now = datetime.now(timezone.utc)
        company_id = uuid4()
        invitation_id = uuid4()
        with self.session_factory() as session:
            session.add(
                Company(
                    id=company_id,
                    name="Resend Company",
                    status=CompanyStatus.PENDING_ACTIVATION,
                )
            )
            session.flush()
            session.add(
                Invitation(
                    id=invitation_id,
                    company_id=company_id,
                    invited_name="Invitee",
                    email="invitee@example.com",
                    intended_role=CompanyRole.COMPANY_ADMIN,
                    token_hash="previous-token-hash",
                    status=InvitationStatus.EXPIRED,
                    expires_at=now - timedelta(hours=1),
                    created_at=now - timedelta(hours=1),
                )
            )
            session.flush()
            session.add(
                InvitationEmailOutbox(
                    invitation_id=invitation_id,
                    status=OutboxStatus.PENDING,
                    attempts=1,
                    next_attempt_at=now - timedelta(minutes=2),
                    created_at=now - timedelta(minutes=2),
                )
            )
            session.commit()

        listing = self.client.get(
            f"/company-onboarding/companies/{company_id}/invitations",
            headers=self.root_headers,
        )
        resend = self.client.post(
            f"/company-onboarding/invitations/{invitation_id}/resend",
            headers=self.root_headers,
        )
        rate_limited = self.client.post(
            f"/company-onboarding/invitations/{invitation_id}/resend",
            headers=self.root_headers,
        )
        revoked = self.client.post(
            f"/company-onboarding/invitations/{invitation_id}/revoke",
            headers=self.root_headers,
        )

        self.assertEqual(200, listing.status_code)
        self.assertEqual(InvitationStatus.EXPIRED.value, listing.json()[0]["status"])
        self.assertNotIn("token_hash", listing.json()[0])
        self.assertEqual(200, resend.status_code)
        self.assertNotIn("token", resend.json())
        self.assertEqual(OutboxStatus.PENDING.value, resend.json()["email_delivery_status"])
        self.assertEqual(429, rate_limited.status_code)
        self.assertEqual(200, revoked.status_code)
        self.assertEqual(InvitationStatus.REVOKED.value, revoked.json()["status"])
        with self.session_factory() as session:
            invitation = session.get(Invitation, invitation_id)
            events = session.scalars(
                select(InvitationEmailOutbox)
                .where(InvitationEmailOutbox.invitation_id == invitation_id)
                .order_by(InvitationEmailOutbox.created_at)
            ).all()
            self.assertEqual(InvitationStatus.REVOKED.value, invitation.status)
            self.assertNotEqual("previous-token-hash", invitation.token_hash)
            self.assertEqual(2, len(events))
            self.assertEqual(OutboxStatus.FAILED.value, events[0].status)
            self.assertEqual(OutboxStatus.FAILED.value, events[1].status)

    def _login(self, email: str, password: str) -> dict[str, str]:
        response = self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(200, response.status_code)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}


if __name__ == "__main__":
    unittest.main()
