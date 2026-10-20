from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID
import unittest

from app.src.application.usecases.accept_invitation import AcceptInvitationUseCase
from app.src.application.usecases.get_invitation_acceptance_context import (
    GetInvitationAcceptanceContextUseCase,
)
from app.src.domain.dtos.company_onboarding import (
    AcceptedInvitation,
    InvitationAcceptanceContext,
)
from app.src.domain.dtos.authentication import IssuedAccessToken
from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.company_onboarding.errors import (
    InvitationNotFoundError,
)


class FakeUnitOfWork:
    @contextmanager
    def transaction(self):
        yield


class FakeRepository:
    def __init__(self):
        self.context = InvitationAcceptanceContext(
            invitation_id=UUID("00000000-0000-0000-0000-000000000201"),
            company_id=UUID("00000000-0000-0000-0000-000000000202"),
            company_name="Acme",
            invited_name="Ana",
            email="ana@example.com",
            intended_role=CompanyRole.COMPANY_ADMIN,
            expires_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
        )
        self.accepted = None
        self.missing = False

    def get_invitation_acceptance_context(self, token_hash, now):
        if self.missing:
            raise InvitationNotFoundError()
        return self.context

    def accept_invitation(self, token_hash, now):
        if self.missing:
            raise InvitationNotFoundError()
        self.accepted = (token_hash, now)
        return AcceptedInvitation(
            invitation_id=self.context.invitation_id,
            company_id=self.context.company_id,
            company_name=self.context.company_name,
            user_id=UUID("00000000-0000-0000-0000-000000000203"),
        )


class FakeTokenIssuer:
    def hash(self, token):
        return f"hash:{token}"


class FakeAccessTokenProvider:
    def __init__(self):
        self.issued_for = []

    def issue(self, user_id):
        self.issued_for.append(user_id)
        return IssuedAccessToken(encoded="signed-access-token", expires_in=300)

    def decode_subject(self, token):
        raise NotImplementedError


class AcceptInvitationUseCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeRepository()
        self.access_tokens = FakeAccessTokenProvider()
        self.use_case = AcceptInvitationUseCase(
            repository=self.repository,
            token_issuer=FakeTokenIssuer(),
            access_tokens=self.access_tokens,
            unit_of_work=FakeUnitOfWork(),
        )

    def test_accepts_invitation_and_issues_access_token_after_acceptance(self) -> None:
        result = self.use_case.execute("bearer-token")

        self.assertEqual("hash:bearer-token", self.repository.accepted[0])
        self.assertEqual(self.repository.context.company_id, result.company_id)
        self.assertEqual("signed-access-token", result.access_token)
        self.assertEqual(300, result.expires_in)
        self.assertEqual([result.user_id], self.access_tokens.issued_for)

    def test_invalid_token_does_not_create_an_account(self) -> None:
        self.repository.missing = True

        with self.assertRaises(InvitationNotFoundError):
            self.use_case.execute("invalid-token")

        self.assertIsNone(self.repository.accepted)
        self.assertEqual([], self.access_tokens.issued_for)

    def test_validation_returns_only_context_for_a_hashed_token(self) -> None:
        use_case = GetInvitationAcceptanceContextUseCase(
            repository=self.repository,
            token_issuer=FakeTokenIssuer(),
            unit_of_work=FakeUnitOfWork(),
        )

        context = use_case.execute("bearer-token")

        self.assertEqual(self.repository.context, context)


if __name__ == "__main__":
    unittest.main()
