from email.message import EmailMessage
from unittest.mock import patch
import unittest

from app.src.domain.dtos.company_onboarding import InvitationEmailMessage
from app.src.infra.adapters.email.smtp_invitation_sender import (
    SmtpInvitationEmailSender,
)
from app.src.infra.setup.settings import Settings


class SmtpInvitationEmailSenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            app_env="test",
            invitation_base_url="https://app.example.com/accept-invitation",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="mailer",
            smtp_password="mail-password",
            smtp_from_email="noreply@example.com",
        )

    @patch("app.src.infra.adapters.email.smtp_invitation_sender.smtplib.SMTP")
    def test_uses_starttls_and_sends_plain_and_html_content(self, smtp_type) -> None:
        client = smtp_type.return_value.__enter__.return_value
        message = InvitationEmailMessage(
            recipient="ana@example.com",
            subject="OrbiBots invite",
            text_body="Secure link",
            html_body="<p>Secure link</p>",
            message_id="<message@orbibots>",
        )

        SmtpInvitationEmailSender(self.settings).send(message)

        client.starttls.assert_called_once()
        client.login.assert_called_once_with("mailer", "mail-password")
        sent_message = client.send_message.call_args.args[0]
        self.assertIsInstance(sent_message, EmailMessage)
        self.assertEqual("ana@example.com", sent_message["To"])
        self.assertEqual("<message@orbibots>", sent_message["Message-ID"])
        self.assertEqual(2, len(list(sent_message.iter_parts())))

    @patch("app.src.infra.adapters.email.smtp_invitation_sender.smtplib.SMTP_SSL")
    def test_uses_smtp_ssl_on_port_465(self, smtp_ssl_type) -> None:
        client = smtp_ssl_type.return_value.__enter__.return_value
        sender = SmtpInvitationEmailSender(
            Settings(
                app_env="test",
                invitation_base_url="https://app.example.com/accept-invitation",
                smtp_host="smtp.example.com",
                smtp_port=465,
                smtp_from_email="noreply@example.com",
            )
        )
        message = InvitationEmailMessage(
            recipient="ana@example.com",
            subject="OrbiBots invite",
            text_body="Secure link",
            html_body="<p>Secure link</p>",
            message_id="<message@orbibots>",
        )

        sender.send(message)

        smtp_ssl_type.assert_called_once()
        client.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
