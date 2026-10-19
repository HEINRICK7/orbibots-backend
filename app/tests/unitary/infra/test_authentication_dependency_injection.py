import unittest
from unittest.mock import Mock
from uuid import uuid4

from app.src.domain.dtos.authentication import IssuedAccessToken, UserCredentials
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.interfaces.adapters.authentication import (
    AccessTokenProvider,
    PasswordVerifier,
)
from app.src.domain.interfaces.gateways.authentication import (
    UserAuthenticationRepository,
)
from app.src.infra.di.authentication import AuthenticationUseCaseProvider
from app.src.infra.di.container import create_container
from app.src.infra.setup.settings import Settings


class AuthenticationDependencyInjectionTests(unittest.TestCase):
    def test_punq_composes_use_case_with_mocked_boundary_dependencies(self) -> None:
        user = AuthenticatedUser(
            id=uuid4(),
            name="Test User",
            email="test@example.test",
            is_active=True,
        )
        repository = Mock(spec=UserAuthenticationRepository)
        repository.get_credentials_by_email.return_value = UserCredentials(
            user=user,
            password_hash="encoded-password",
        )
        verifier = Mock(spec=PasswordVerifier)
        verifier.verify.return_value = True
        tokens = Mock(spec=AccessTokenProvider)
        tokens.issue.return_value = IssuedAccessToken(
            encoded="mock-token",
            expires_in=60,
        )
        session = object()
        repository_factory = Mock(return_value=repository)
        container = create_container(
            Settings(app_env="test"),
            overrides={
                PasswordVerifier: verifier,
                AccessTokenProvider: tokens,
            },
        )
        provider = AuthenticationUseCaseProvider(
            container,
            repository_factory=repository_factory,
        )

        result = provider.login(session).execute(user.email, "plain-password")

        self.assertEqual(result.encoded, "mock-token")
        self.assertEqual(result.expires_in, 60)
        repository_factory.assert_called_once_with(session)
        repository.get_credentials_by_email.assert_called_once_with(user.email)
        verifier.verify.assert_called_once_with("plain-password", "encoded-password")
        tokens.issue.assert_called_once_with(user.id)


if __name__ == "__main__":
    unittest.main()
