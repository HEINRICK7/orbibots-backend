from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID
import unittest

from app.src.application.usecases.resend_invitation import ResendInvitationUseCase
from app.src.application.usecases.revoke_invitation import RevokeInvitationUseCase
from app.src.application.usecases.list_company_invitations import (
    ListCompanyInvitationsUseCase,
)
from app.src.domain.dtos.company_onboarding import (
    PreparedInvitationResend,
    RevokedInvitation,
)
from app.src.domain.entities.access.errors import AccessDeniedError
from app.src.domain.entities.authentication.global_role import GlobalRole
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.entities.company_onboarding.errors import (
    InvitationRateLimitError,
    InvitationStateError,
)


class FakeUnitOfWork:
    @contextmanager
    def transaction(self):
        yield


class FakeAuthorizer:
    def execute(self, actor):
        if actor.global_role is not GlobalRole.ADMIN:
            raise AccessDeniedError("Global ADMIN role required.")


class FakeTokenIssuer:
    def issue(self):
        from app.src.domain.dtos.company_onboarding import IssuedInvitationToken

        return IssuedInvitationToken("new-token", "new-hash")


class FakeRepository:
    def __init__(self):
        self.resend_args = None
        self.revoke_args = None
        self.audits = []
        self.resend_error = None
        self.revoke_error = None
        self.listed_company_id = None

    def prepare_invitation_resend(
        self, invitation_id, now, token_hash, expires_at, minimum_interval
    ):
        self.resend_args = (invitation_id, token_hash, expires_at, minimum_interval)
        if self.resend_error:
            raise self.resend_error
        return PreparedInvitationResend(
            invitation_id=invitation_id,
            company_id=UUID("00000000-0000-0000-0000-000000000302"),
            outbox_id=UUID("00000000-0000-0000-0000-000000000303"),
            company_name="Acme",
            invited_name="Ana",
            email="ana@example.com",
            expires_at=expires_at,
        )

    def revoke_invitation(self, invitation_id, now):
        self.revoke_args = (invitation_id, now)
        if self.revoke_error:
            raise self.revoke_error
        return RevokedInvitation(
            invitation_id=invitation_id,
            company_id=UUID("00000000-0000-0000-0000-000000000302"),
        )

    def create_audit_event(self, actor_user_id, company_id, action, outcome):
        self.audits.append((actor_user_id, company_id, action, outcome))

    def list_company_invitations(self, company_id):
        self.listed_company_id = company_id
        return ()


class ManageInvitationsUseCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeRepository()
        self.actor = AuthenticatedUser(
            id=UUID("00000000-0000-0000-0000-000000000301"),
            name="Root",
            email="root@example.com",
            is_active=True,
            global_role=GlobalRole.ADMIN,
        )
        self.resend = ResendInvitationUseCase(
            repository=self.repository,
            token_issuer=FakeTokenIssuer(),
            require_global_admin=FakeAuthorizer(),
            unit_of_work=FakeUnitOfWork(),
        )
        self.revoke = RevokeInvitationUseCase(
            repository=self.repository,
            require_global_admin=FakeAuthorizer(),
            unit_of_work=FakeUnitOfWork(),
        )

    def test_resends_with_new_hash_and_one_day_expiry(self) -> None:
        before = datetime.now(timezone.utc)
        invitation_id = UUID("00000000-0000-0000-0000-000000000304")

        result = self.resend.execute(self.actor, invitation_id)

        after = datetime.now(timezone.utc)
        self.assertEqual(invitation_id, result.invitation_id)
        self.assertEqual("new-token", result.raw_token)
        self.assertEqual("new-hash", self.repository.resend_args[1])
        self.assertEqual(timedelta(minutes=1), self.repository.resend_args[3])
        self.assertGreaterEqual(result.expires_at, before + timedelta(hours=24))
        self.assertLessEqual(result.expires_at, after + timedelta(hours=24))
        self.assertEqual("invitation.resend", self.repository.audits[0][2])

    def test_rate_limit_is_preserved_and_no_audit_is_written(self) -> None:
        self.repository.resend_error = InvitationRateLimitError()

        with self.assertRaises(InvitationRateLimitError):
            self.resend.execute(
                self.actor,
                UUID("00000000-0000-0000-0000-000000000304"),
            )

        self.assertEqual([], self.repository.audits)

    def test_revoke_records_audit(self) -> None:
        invitation_id = UUID("00000000-0000-0000-0000-000000000304")

        result = self.revoke.execute(self.actor, invitation_id)

        self.assertEqual(invitation_id, result.invitation_id)
        self.assertEqual("invitation.revoke", self.repository.audits[0][2])

    def test_accepted_invitation_cannot_be_revoked(self) -> None:
        self.repository.revoke_error = InvitationStateError()

        with self.assertRaises(InvitationStateError):
            self.revoke.execute(
                self.actor,
                UUID("00000000-0000-0000-0000-000000000304"),
            )

        self.assertEqual([], self.repository.audits)

    def test_global_admin_can_list_invitation_status_for_a_company(self) -> None:
        use_case = ListCompanyInvitationsUseCase(
            repository=self.repository,
            require_global_admin=FakeAuthorizer(),
        )
        company_id = UUID("00000000-0000-0000-0000-000000000302")

        result = use_case.execute(self.actor, company_id)

        self.assertEqual((), result)
        self.assertEqual(company_id, self.repository.listed_company_id)


if __name__ == "__main__":
    unittest.main()
