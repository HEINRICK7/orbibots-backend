from app.src.domain.dtos.company_onboarding import IssuedInvitationToken
from typing import Protocol

from app.src.domain.dtos.company_onboarding import InvitationEmailMessage


class InvitationTokenIssuer(Protocol):
    def issue(self) -> IssuedInvitationToken: ...

    def hash(self, raw_token: str) -> str: ...


class InvitationEmailSender(Protocol):
    def send(self, message: InvitationEmailMessage) -> None: ...
