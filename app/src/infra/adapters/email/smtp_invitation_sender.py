from email.message import EmailMessage
from email.utils import formataddr
import smtplib
import ssl

from app.src.domain.dtos.company_onboarding import InvitationEmailMessage
from app.src.domain.interfaces.adapters.company_onboarding import InvitationEmailSender
from app.src.infra.setup.settings import Settings


class SmtpInvitationEmailSender(InvitationEmailSender):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: InvitationEmailMessage) -> None:
        email = EmailMessage()
        email["Subject"] = message.subject
        email["From"] = formataddr(("OrbiBots", self._settings.smtp_from_email))
        email["To"] = message.recipient
        email["Message-ID"] = message.message_id
        email.set_content(message.text_body)
        email.add_alternative(message.html_body, subtype="html")

        context = ssl.create_default_context()
        if self._settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                self._settings.smtp_host,
                self._settings.smtp_port,
                context=context,
                timeout=15,
            ) as client:
                self._authenticate(client)
                client.send_message(email)
            return

        with smtplib.SMTP(
            self._settings.smtp_host,
            self._settings.smtp_port,
            timeout=15,
        ) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
            self._authenticate(client)
            client.send_message(email)

    def _authenticate(self, client: smtplib.SMTP) -> None:
        username = self._settings.smtp_username
        password = self._settings.smtp_password
        if username and password:
            client.login(username, password)
