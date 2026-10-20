from app.src.domain.dtos.company_onboarding import IssuedInvitationToken
from typing import Protocol


class InvitationTokenIssuer(Protocol):
    def issue(self) -> IssuedInvitationToken: ...

    def hash(self, raw_token: str) -> str: ...
