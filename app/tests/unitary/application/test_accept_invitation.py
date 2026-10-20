from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
import unittest

from app.src.application.usecases.accept_invitation import AcceptInvitationUseCase
from app.src.domain.dtos.company_onboarding import (
    AcceptedInvitation,
    InvitationAcceptanceContext,
)
from app.src.domain.entities.company_onboarding.errors import (
    InvalidCompanyOnboardingInputError,
    InvitationNotFoundError,
)


class FakeUnitOfWork:
    @contextmanager
    def transaction(self):
        yield


class FakeRepository:
    def __init__(self, *, requires_password_setup=True):
        self.context = InvitationAcceptanceContext(
            invitation_id=UUID("00000000-0000-0000-0000-000000000201"),
            company_id=UUID("00000000-0000-0000-0000-000000000202"),
            company_name="Acme",
            invited_name="Ana",
            email="ana@example.com",
            expires_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
            requires_password_setup=requires_password_setup,
        )
        self.accepted = None
        self.missing = False

    def get_invitation_acceptance_context(self, token_hash, now):
        if self.missing:
            raise InvitationNotFoundError()
        return self.context

    def accept_invitation(self, token_hash, now, password_hash):
        self.accepted = (token_hash, password_hash)
        return AcceptedInvitation(
            invitation_id=self.context.invitation_id,
            company_id=self.context.company_id,
            company_name=self.context.company_name,
            user_id=UUID("00000000-0000-0000-0000-000000000203"),
        )


class FakeTokenIssuer:
    def hash(self, token):
        return f"hash:{token}"


@dataclass
class FakePasswordHasher:
    calls: list[str] | None = None

    def __post_init__(self):
        self.calls = []

    def hash(self, password):
        self.calls.append(password)
        return f"password-hash:{password}"


class AcceptInvitationUseCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeRepository()
        self.password_hasher = FakePasswordHasher()
        self.use_case = AcceptInvitationUseCase(
            repository=self.repository,
            token_issuer=FakeTokenIssuer(),
            password_hasher=self.password_hasher,
            unit_of_work=FakeUnitOfWork(),
        )

    def test_accepts_invitation_and_hashes_password_for_new_user(self) -> None:
        result = self.use_case.execute("bearer-token", "a-long-password-value")

        self.assertEqual("hash:bearer-token", self.repository.accepted[0])
        self.assertEqual("password-hash:a-long-password-value", self.repository.accepted[1])
        self.assertEqual(["a-long-password-value"], self.password_hasher.calls)
        self.assertEqual(self.repository.context.company_id, result.company_id)

    def test_existing_user_keeps_password_and_does_not_need_password_input(self) -> None:
        self.repository = FakeRepository(requires_password_setup=False)
        self.use_case = AcceptInvitationUseCase(
            repository=self.repository,
            token_issuer=FakeTokenIssuer(),
            password_hasher=self.password_hasher,
            unit_of_work=FakeUnitOfWork(),
        )

        self.use_case.execute("bearer-token", None)

        self.assertEqual(("hash:bearer-token", None), self.repository.accepted)
        self.assertEqual([], self.password_hasher.calls)

    def test_new_user_must_set_a_password(self) -> None:
        with self.assertRaises(InvalidCompanyOnboardingInputError):
            self.use_case.execute("bearer-token", None)

        self.assertIsNone(self.repository.accepted)

    def test_rejects_short_password(self) -> None:
        with self.assertRaises(InvalidCompanyOnboardingInputError):
            self.use_case.execute("bearer-token", "short")

        self.assertIsNone(self.repository.accepted)

    def test_invalid_token_does_not_create_an_account(self) -> None:
        self.repository.missing = True

        with self.assertRaises(InvitationNotFoundError):
            self.use_case.execute("invalid-token", "a-long-password-value")

        self.assertIsNone(self.repository.accepted)
        self.assertEqual([], self.password_hasher.calls)


if __name__ == "__main__":
    unittest.main()
