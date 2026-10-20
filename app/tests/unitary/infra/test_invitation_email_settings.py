import unittest

from app.src.infra.exceptions.errors import ConfigurationError
from app.src.infra.setup.settings import Settings


class InvitationEmailSettingsTests(unittest.TestCase):
    def test_email_delivery_is_configured_only_with_host_sender_and_url(self) -> None:
        settings = Settings(
            app_env="test",
            invitation_base_url="http://localhost:3000/accept-invitation",
            smtp_host="smtp.example.com",
            smtp_from_email="noreply@example.com",
        )

        self.assertTrue(settings.invitation_email_configured)

    def test_rejects_partial_smtp_configuration(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings(app_env="test", smtp_host="smtp.example.com")

    def test_requires_https_invitation_link_in_public_environments(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings(
                app_env="production",
                database_url="postgresql://localhost/orbibots",
                jwt_secret_key="x" * 32,
                invitation_base_url="http://app.example.com/accept-invitation",
                smtp_host="smtp.example.com",
                smtp_from_email="noreply@example.com",
            )

    def test_requires_email_delivery_configuration_in_public_environments(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings(
                app_env="production",
                database_url="postgresql://localhost/orbibots",
                jwt_secret_key="x" * 32,
                invitation_base_url="https://app.example.com/accept-invitation",
            )


if __name__ == "__main__":
    unittest.main()
