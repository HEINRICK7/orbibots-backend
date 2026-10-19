import unittest
from uuid import UUID, uuid4

from src.application.authentication.ports import (
    IssuedAccessToken,
    UserCredentials,
)
from src.application.authentication.use_cases.authenticate_user import (
    AuthenticateUserUseCase,
)
from src.application.authentication.use_cases.login import LoginUseCase
from src.domain.authentication.errors import AuthenticationError
from src.domain.authentication.user import AuthenticatedUser


class InMemoryUserRepository:
    def __init__(self, credentials: UserCredentials) -> None:
        self.credentials = credentials

    def get_credentials_by_email(self, email: str) -> UserCredentials | None:
        return self.credentials if email == self.credentials.user.email else None

    def get_by_id(self, user_id: UUID) -> AuthenticatedUser | None:
        return self.credentials.user if user_id == self.credentials.user.id else None


class TestPasswordVerifier:
    def verify(self, password: str, encoded_hash: str) -> bool:
        return password == "correct-password" and encoded_hash == "encoded-password"


class TestAccessTokens:
    def issue(self, user_id: UUID) -> IssuedAccessToken:
        return IssuedAccessToken(encoded=f"token:{user_id}", expires_in=60)

    def decode_subject(self, token: str) -> UUID:
        if not token.startswith("token:"):
            raise ValueError
        return UUID(token.removeprefix("token:"))


class AuthenticationApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user = AuthenticatedUser(
            id=uuid4(),
            name="Test User",
            email="test@example.test",
            is_active=True,
        )
        self.repository = InMemoryUserRepository(
            UserCredentials(user=self.user, password_hash="encoded-password")
        )
        self.login_use_case = LoginUseCase(
            self.repository,
            TestPasswordVerifier(),
            TestAccessTokens(),
        )
        self.authenticate_use_case = AuthenticateUserUseCase(
            self.repository,
            TestAccessTokens(),
        )

    def test_login_runs_without_database_or_http_framework(self) -> None:
        token = self.login_use_case.execute(self.user.email, "correct-password")

        self.assertEqual(token.encoded, f"token:{self.user.id}")
        self.assertEqual(token.expires_in, 60)

    def test_authenticate_resolves_user_from_access_token(self) -> None:
        authenticated_user = self.authenticate_use_case.execute(f"token:{self.user.id}")

        self.assertEqual(authenticated_user, self.user)

    def test_invalid_password_is_rejected(self) -> None:
        with self.assertRaises(AuthenticationError):
            self.login_use_case.execute(self.user.email, "wrong-password")


if __name__ == "__main__":
    unittest.main()
