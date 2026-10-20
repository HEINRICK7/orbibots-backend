from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
import unittest

from app.src.application.usecases.send_invitation_email import (
    SendInvitationEmailUseCase,
)
from app.src.domain.dtos.company_onboarding import (
    InvitationEmailJob,
    InvitationEmailMessage,
    IssuedInvitationToken,
)
from app.src.domain.entities.company_onboarding.status import OutboxStatus


class FakeUnitOfWork:
    @contextmanager
    def transaction(self):
        yield


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.status = OutboxStatus.PENDING
        self.attempts = 0
        self.claimed_token_hash = "initial-hash"
        self.claimed = []
        self.completed = []
        self.retries = []
        self.job = InvitationEmailJob(
            outbox_id=UUID("00000000-0000-0000-0000-000000000101"),
            invitation_id=UUID("00000000-0000-0000-0000-000000000102"),
            company_name="Acme",
            invited_name="Ana",
            email="ana@example.com",
            status=OutboxStatus.PENDING,
            attempts=0,
            expires_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
        )

    def claim_invitation_email(
        self, outbox_id, now, stale_before, token_hash=None, expires_at=None
    ):
        if self.status is OutboxStatus.SENT:
            return None
        self.attempts += 1
        self.status = OutboxStatus.PROCESSING
        if token_hash is not None:
            self.claimed_token_hash = token_hash
            self.job = InvitationEmailJob(
                **{
                    **self.job.__dict__,
                    "expires_at": expires_at,
                }
            )
        self.claimed.append((outbox_id, token_hash, expires_at))
        return InvitationEmailJob(
            **{
                **self.job.__dict__,
                "status": OutboxStatus.PROCESSING,
                "attempts": self.attempts,
            }
        )

    def mark_invitation_email_sent(self, outbox_id, delivered_at):
        self.status = OutboxStatus.SENT
        self.completed.append((outbox_id, delivered_at))

    def schedule_invitation_email_retry(self, outbox_id, attempted_at, retry_at):
        self.status = OutboxStatus.PENDING
        self.retries.append((outbox_id, attempted_at, retry_at))

    def list_pending_invitation_emails(self, now, limit):
        return (self.job.outbox_id,) if self.status is OutboxStatus.PENDING else ()


class FakeTokenIssuer:
    def __init__(self) -> None:
        self.issued = 0

    def issue(self):
        self.issued += 1
        return IssuedInvitationToken(
            raw_token=f"fresh-token-{self.issued}",
            token_hash=f"fresh-hash-{self.issued}",
        )

    def hash(self, raw_token):
        return f"hash:{raw_token}"


@dataclass
class FakeSender:
    fail: bool = False
    sent: list[InvitationEmailMessage] | None = None

    def __post_init__(self):
        self.sent = []

    def send(self, message):
        if self.fail:
            raise RuntimeError("mail provider failure")
        self.sent.append(message)


class SendInvitationEmailUseCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeOutboxRepository()
        self.token_issuer = FakeTokenIssuer()
        self.sender = FakeSender()
        self.use_case = SendInvitationEmailUseCase(
            repository=self.repository,
            token_issuer=self.token_issuer,
            email_sender=self.sender,
            unit_of_work=FakeUnitOfWork(),
            invitation_base_url="https://app.example.com/accept-invitation",
        )

    def test_sends_link_once_then_marks_outbox_sent_without_exposing_token_in_result(self) -> None:
        outbox_id = self.repository.job.outbox_id

        result = self.use_case.execute(outbox_id, raw_token="one-time-token")

        self.assertTrue(result.sent)
        self.assertEqual(1, len(self.sender.sent))
        self.assertIn("token=one-time-token", self.sender.sent[0].text_body)
        self.assertIn("Acme", self.sender.sent[0].text_body)
        self.assertEqual(OutboxStatus.SENT, self.repository.status)
        self.assertEqual([(outbox_id, None, None)], self.repository.claimed)
        self.assertNotIn("one-time-token", repr(result))

        duplicate = self.use_case.execute(outbox_id)

        self.assertFalse(duplicate.sent)
        self.assertEqual(1, len(self.sender.sent))

    def test_failed_delivery_is_retryable_and_retry_rotates_hash(self) -> None:
        self.sender.fail = True
        outbox_id = self.repository.job.outbox_id

        failed = self.use_case.execute(outbox_id, raw_token="first-token")

        self.assertFalse(failed.sent)
        self.assertEqual(1, len(self.repository.retries))
        self.assertEqual(OutboxStatus.PENDING, self.repository.status)
        self.assertNotIn("first-token", repr(self.repository.retries))

        self.sender.fail = False
        delivered = self.use_case.execute(outbox_id)

        self.assertTrue(delivered.sent)
        self.assertEqual("fresh-hash-1", self.repository.claimed_token_hash)
        self.assertIn("token=fresh-token-1", self.sender.sent[0].text_body)
        self.assertEqual(2, len(self.repository.claimed))

    def test_pending_dispatch_reprocesses_outbox_jobs(self) -> None:
        count = self.use_case.dispatch_pending(limit=10)

        self.assertEqual(1, count)
        self.assertEqual(1, len(self.sender.sent))


if __name__ == "__main__":
    unittest.main()
