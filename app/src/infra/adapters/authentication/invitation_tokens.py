import hashlib
import secrets

from app.src.domain.dtos.company_onboarding import IssuedInvitationToken
from app.src.domain.interfaces.adapters.company_onboarding import InvitationTokenIssuer


class SecureInvitationTokenIssuer(InvitationTokenIssuer):
    def issue(self) -> IssuedInvitationToken:
        token = secrets.token_urlsafe(32)
        return IssuedInvitationToken(raw_token=token, token_hash=self.hash(token))

    def hash(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
