from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.src.domain.interfaces.adapters.authentication import (
    PasswordHasher,
    PasswordVerifier,
)

class PasswordHashFactory:
    def create(self) -> PasswordHash:
        return PasswordHash.recommended()


class PwdlibPasswordVerifier(PasswordVerifier):
    def __init__(self, password_hash: PasswordHash) -> None:
        self._password_hash = password_hash

    def verify(self, password: str, encoded_hash: str) -> bool:
        try:
            return self._password_hash.verify(password, encoded_hash)
        except UnknownHashError:
            return False


class PwdlibPasswordHasher(PasswordHasher):
    def __init__(self, password_hash: PasswordHash) -> None:
        self._password_hash = password_hash

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)
