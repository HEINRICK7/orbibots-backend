import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from app.src.domain.interfaces.gateways.authentication import GlobalAdminGrantRepository
from app.src.application.usecases.grant_global_admin import (
    GlobalAdminAllowlist,
    GrantGlobalAdminUseCase,
)
from app.src.domain.entities.authentication.errors import GlobalAdminGrantError
from app.src.domain.entities.authentication.global_role import GlobalRole
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.infra.setup.settings import ConfigurationError, Settings


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

    def test_allowlist_accepts_one_or_two_distinct_valid_emails(self) -> None:
        GlobalAdminAllowlist(("solo@example.test",))
        GlobalAdminAllowlist(("first@example.test", "second@example.test"))

    def test_allowlist_rejects_empty_duplicate_invalid_or_more_than_two_emails(self) -> None:
        invalid_allowlists = (
            (),
            ("first@example.test", "FIRST@example.test"),
            ("first@example.test", "invalid-email"),
            ("first@example.test", "second@example.test", "third@example.test"),
        )

        for emails in invalid_allowlists:
            with self.subTest(emails=emails):
                with self.assertRaises(GlobalAdminGrantError):
                    GlobalAdminAllowlist(emails)

    def test_bootstrap_identity_must_be_explicitly_allowlisted(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings(
                app_env="development",
                bootstrap_admin_email="admin@example.test",
                bootstrap_admin_password="long-enough-development-password",
            )

    def test_bootstrap_password_requires_twenty_characters(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings(
                app_env="development",
                bootstrap_admin_email="admin@example.test",
                bootstrap_admin_password="too-short",
                global_admin_allowed_emails=("admin@example.test",),
            )

    def test_bootstrap_identity_can_be_the_only_allowlisted_global_admin(self) -> None:
        settings = Settings(
            app_env="development",
            bootstrap_admin_email="Admin@example.test",
            bootstrap_admin_password="long-enough-development-password",
            global_admin_allowed_emails=("admin@example.test",),
        )

        self.assertEqual(settings.global_admin_allowed_emails, ("admin@example.test",))

    def test_settings_do_not_silently_ignore_empty_allowlist_entries(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GLOBAL_ADMIN_ALLOWED_EMAILS":
                    "first@example.test,second@example.test,",
                "BOOTSTRAP_ADMIN_EMAIL": "",
                "BOOTSTRAP_ADMIN_PASSWORD": "",
            },
        ):
            settings = Settings.from_environment()

        with self.assertRaises(GlobalAdminGrantError):
            GlobalAdminAllowlist(settings.global_admin_allowed_emails)


if __name__ == "__main__":
    unittest.main()
