import re
from collections.abc import Iterable

from app.contexts.authentication.application.ports import GlobalAdminGrantRepository
from app.contexts.authentication.domain.errors import GlobalAdminGrantError
from app.contexts.authentication.domain.user import AuthenticatedUser


class GlobalAdminAllowlist:
    _email_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def __init__(self, allowed_emails: Iterable[str]) -> None:
        normalized_emails = tuple(
            self.normalize_email(email) for email in allowed_emails
        )
        if len(normalized_emails) != 2 or len(set(normalized_emails)) != 2:
            raise GlobalAdminGrantError(
                "Global-admin allowlist must contain exactly two distinct email addresses."
            )
        self._allowed_emails = frozenset(normalized_emails)

    def normalize_email(self, email: str) -> str:
        normalized_email = email.strip().lower()
        if not self._email_pattern.fullmatch(normalized_email):
            raise GlobalAdminGrantError(
                "Global-admin allowlist entries must be valid email addresses."
            )
        return normalized_email

    def ensure_allowed(self, email: str) -> str:
        normalized_email = self.normalize_email(email)
        if normalized_email not in self._allowed_emails:
            raise GlobalAdminGrantError(
                "This identity is not allowed to receive global ADMIN."
            )
        return normalized_email

    def matches(self, emails: Iterable[str]) -> bool:
        try:
            normalized_emails = tuple(self.normalize_email(email) for email in emails)
        except GlobalAdminGrantError:
            return False
        return len(normalized_emails) == 2 and frozenset(normalized_emails) == self._allowed_emails


class GrantGlobalAdminUseCase:
    def __init__(
        self,
        repository: GlobalAdminGrantRepository,
        allowlist: GlobalAdminAllowlist,
    ) -> None:
        self._repository = repository
        self._allowlist = allowlist

    def execute(self, email: str) -> AuthenticatedUser:
        allowed_email = self._allowlist.ensure_allowed(email)
        return self._repository.grant_global_admin(allowed_email)
