from datetime import datetime, timezone
from unittest import TestCase
from uuid import UUID

from app.src.application.usecases.list_company_onboarding import (
    ListCompanyOnboardingUseCase,
)
from app.src.domain.dtos.company_onboarding import CompanyOnboardingSummary
from app.src.domain.entities.access.errors import AccessDeniedError
from app.src.domain.entities.authentication.global_role import GlobalRole
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.entities.company_onboarding.status import CompanyStatus


class FakeAuthorizer:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def execute(self, actor):
        if not self.allowed:
            raise AccessDeniedError("Global ADMIN role required.")


class FakeRepository:
    def __init__(self, result):
        self.result = result
        self.listed = False

    def list_company_onboarding(self):
        self.listed = True
        return self.result


class ListCompanyOnboardingUseCaseTests(TestCase):
    def setUp(self):
        self.actor = AuthenticatedUser(
            id=UUID("00000000-0000-0000-0000-000000000401"),
            name="Root",
            email="root@example.com",
            is_active=True,
            global_role=GlobalRole.ADMIN,
        )
        self.summary = CompanyOnboardingSummary(
            id=UUID("00000000-0000-0000-0000-000000000402"),
            name="Acme",
            status=CompanyStatus.PENDING_ACTIVATION,
            created_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
            activated_at=None,
            invitations=(),
        )

    def test_lists_company_and_invitation_summaries_for_a_global_admin(self):
        repository = FakeRepository((self.summary,))
        use_case = ListCompanyOnboardingUseCase(repository, FakeAuthorizer())

        result = use_case.execute(self.actor)

        self.assertEqual((self.summary,), result)
        self.assertTrue(repository.listed)

    def test_denies_before_reading_companies_when_actor_is_not_global_admin(self):
        repository = FakeRepository((self.summary,))
        use_case = ListCompanyOnboardingUseCase(repository, FakeAuthorizer(allowed=False))

        with self.assertRaises(AccessDeniedError):
            use_case.execute(self.actor)

        self.assertFalse(repository.listed)
