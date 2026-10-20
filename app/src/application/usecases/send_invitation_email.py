from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from uuid import UUID

from app.src.application.gateways.transactions import UnitOfWork
from app.src.domain.dtos.company_onboarding import (
    EmailDispatchResult,
    InvitationEmailJob,
    InvitationEmailMessage,
)
from app.src.domain.interfaces.adapters.company_onboarding import (
    InvitationEmailSender,
    InvitationTokenIssuer,
)
from app.src.domain.interfaces.gateways.company_onboarding import (
    InvitationOutboxRepository,
)


class SendInvitationEmailUseCase:
    invitation_lifetime = timedelta(hours=24)
    claim_timeout = timedelta(minutes=5)

    def __init__(
        self,
        repository: InvitationOutboxRepository,
        token_issuer: InvitationTokenIssuer,
        email_sender: InvitationEmailSender,
        unit_of_work: UnitOfWork,
        invitation_base_url: str,
    ) -> None:
        self._repository = repository
        self._token_issuer = token_issuer
        self._email_sender = email_sender
        self._unit_of_work = unit_of_work
        self._invitation_base_url = invitation_base_url

    def execute(
        self,
        outbox_id: UUID,
        raw_token: str | None = None,
    ) -> EmailDispatchResult:
        now = datetime.now(timezone.utc)
        issued_token = self._token_issuer.issue() if raw_token is None else None
        replacement_hash = issued_token.token_hash if issued_token else None
        replacement_expiry = now + self.invitation_lifetime if issued_token else None

        with self._unit_of_work.transaction():
            job = self._repository.claim_invitation_email(
                outbox_id=outbox_id,
                now=now,
                stale_before=now - self.claim_timeout,
                token_hash=replacement_hash,
                expires_at=replacement_expiry,
            )
        if job is None:
            return EmailDispatchResult(sent=False)

        token = raw_token if raw_token is not None else issued_token.raw_token
        message = self._create_message(job, token)
        try:
            self._email_sender.send(message)
        except Exception:
            retry_at = now + self._retry_delay(job.attempts)
            with self._unit_of_work.transaction():
                self._repository.schedule_invitation_email_retry(
                    outbox_id,
                    attempted_at=now,
                    retry_at=retry_at,
                )
            return EmailDispatchResult(sent=False)

        with self._unit_of_work.transaction():
            self._repository.mark_invitation_email_sent(outbox_id, datetime.now(timezone.utc))
        return EmailDispatchResult(sent=True)

    def dispatch_pending(self, limit: int = 50) -> int:
        if limit < 1:
            return 0
        now = datetime.now(timezone.utc)
        with self._unit_of_work.transaction():
            outbox_ids = self._repository.list_pending_invitation_emails(now, limit)
        delivered = 0
        for outbox_id in outbox_ids:
            if self.execute(outbox_id).sent:
                delivered += 1
        return delivered

    def _create_message(
        self,
        job: InvitationEmailJob,
        raw_token: str,
    ) -> InvitationEmailMessage:
        parts = urlsplit(self._invitation_base_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["token"] = raw_token
        link = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
        expiration = job.expires_at
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        expires_at = expiration.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        subject = f"Convite para {job.company_name} no OrbiBots"
        text_body = (
            f"Olá, {job.invited_name}.\n\n"
            f"Você recebeu um convite para administrar {job.company_name} no OrbiBots.\n"
            f"Acesse o link para aceitar o convite e criar seu acesso:\n{link}\n\n"
            f"Este link expira em {expires_at}. Se você não esperava este convite, ignore este email."
        )
        html_body = (
            f"<p>Olá, {escape(job.invited_name)}.</p>"
            f"<p>Você recebeu um convite para administrar "
            f"<strong>{escape(job.company_name)}</strong> no OrbiBots.</p>"
            f'<p><a href="{escape(link, quote=True)}">Aceitar convite</a></p>'
            f"<p>Este link expira em {escape(expires_at)}. "
            "Se você não esperava este convite, ignore este email.</p>"
        )
        return InvitationEmailMessage(
            recipient=job.email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            message_id=f"<{job.outbox_id}@orbibots>",
        )

    @staticmethod
    def _retry_delay(attempts: int) -> timedelta:
        return timedelta(seconds=min(5 * 2 ** max(attempts - 1, 0), 3600))
