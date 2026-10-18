import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from app.contexts.authentication.application.ports import GlobalAdminGrantRepository
from app.contexts.authentication.application.use_cases.grant_global_admin import (
    GlobalAdminAllowlist,
    GrantGlobalAdminUseCase,
)
from app.contexts.authentication.domain.errors import GlobalAdminGrantError
from app.contexts.authentication.domain.global_role import GlobalRole
from app.contexts.authentication.domain.user import AuthenticatedUser
from app.platform.config import Settings


class GlobalAdminTests(unittest.TestCase):
    def setUp(self) -> None:
        self.allowed_emails = ("first@example.test", "second@example.test")
        self.allowlist = GlobalAdminAllowlist(self.allowed_emails)
        self.repository = Mock(spec=GlobalAdminGrantRepository)
        self.use_case = GrantGlobalAdminUseCase(self.repository, self.allowlist)

    def test_normalizes_emails_before_granting_admin(self) -> None:
        admin = AuthenticatedUser(
            id=uuid4(),
            name="First Admin",
            email=self.allowed_emails[0],
            is_active=True,
            global_role=GlobalRole.ADMIN,
        )
        self.repository.grant_global_admin.return_value = admin

        result = self.use_case.execute(" FIRST@EXAMPLE.TEST ")

        self.assertEqual(result, admin)
        self.repository.grant_global_admin.assert_called_once_with(
            self.allowed_emails[0]
        )

    def test_rejects_an_identity_outside_the_allowlist(self) -> None:
        with self.assertRaises(GlobalAdminGrantError):
            self.use_case.execute("third@example.test")

        self.repository.grant_global_admin.assert_not_called()

    def test_allowlist_requires_exactly_two_distinct_valid_emails(self) -> None:
        invalid_allowlists = (
            ("first@example.test",),
            ("first@example.test", "FIRST@example.test"),
            ("first@example.test", "invalid-email"),
            ("first@example.test", "second@example.test", "third@example.test"),
        )

        for emails in invalid_allowlists:
            with self.subTest(emails=emails):
                with self.assertRaises(GlobalAdminGrantError):
                    GlobalAdminAllowlist(emails)

    def test_settings_do_not_silently_ignore_empty_allowlist_entries(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GLOBAL_ADMIN_ALLOWED_EMAILS":
                    "first@example.test,second@example.test,"
            },
        ):
            settings = Settings.from_environment()

        with self.assertRaises(GlobalAdminGrantError):
            GlobalAdminAllowlist(settings.global_admin_allowed_emails)


if __name__ == "__main__":
    unittest.main()
