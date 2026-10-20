from typing import Protocol
from uuid import UUID

from app.src.domain.dtos.authentication import IssuedAccessToken


class PasswordVerifier(Protocol):
    def verify(self, password: str, encoded_hash: str) -> bool: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...


class AccessTokenProvider(Protocol):
    def issue(self, user_id: UUID) -> IssuedAccessToken: ...

    def decode_subject(self, token: str) -> UUID: ...
