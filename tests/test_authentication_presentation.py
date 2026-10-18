import unittest
from uuid import uuid4
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.contexts.authentication.application.ports import IssuedAccessToken
from app.contexts.authentication.application.use_cases.authenticate_user import (
    AuthenticateUserUseCase,
)
from app.contexts.authentication.application.use_cases.login import LoginUseCase
from app.contexts.authentication.domain.errors import AuthenticationError
from app.contexts.authentication.domain.user import AuthenticatedUser
from app.contexts.authentication.presentation.dependencies import (
    database_session_dependency,
)
from app.contexts.authentication.presentation.router import AuthenticationRouter


class StubSessionDependency:
    def __init__(self) -> None:
        self.session = object()

    def __call__(self) -> object:
        return self.session


class AuthenticationPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.login_use_case = Mock(spec=LoginUseCase)
        self.authenticate_user_use_case = Mock(spec=AuthenticateUserUseCase)
        self.login_use_case_provider = Mock(return_value=self.login_use_case)
        self.authenticate_user_use_case_provider = Mock(
            return_value=self.authenticate_user_use_case
        )
        self.session_dependency = StubSessionDependency()

        self.app = FastAPI()
        self.app.include_router(
            AuthenticationRouter(
                self.login_use_case_provider,
                self.authenticate_user_use_case_provider,
            ).router,
            prefix="/auth",
        )
        self.app.dependency_overrides[database_session_dependency] = (
            self.session_dependency
        )

    def test_routes_resolve_mocked_use_cases_without_database(self) -> None:
        user = AuthenticatedUser(
            id=uuid4(),
            name="Test User",
            email="test@example.test",
            is_active=True,
        )
        self.login_use_case.execute.return_value = IssuedAccessToken(
            encoded="signed-token",
            expires_in=60,
        )
        self.authenticate_user_use_case.execute.return_value = user

        with TestClient(self.app) as client:
            login_response = client.post(
                "/auth/login",
                json={"email": user.email, "password": "password"},
            )
            user_response = client.get(
                "/auth/me",
                headers={"Authorization": "Bearer valid-token"},
            )

        self.assertEqual(
            login_response.json(),
            {
                "access_token": "signed-token",
                "token_type": "bearer",
                "expires_in": 60,
            },
        )
        self.assertEqual(user_response.status_code, 200)
        self.assertEqual(user_response.json()["id"], str(user.id))
        self.login_use_case_provider.assert_called_once()
        self.authenticate_user_use_case_provider.assert_called_once()
        self.assertIs(
            self.login_use_case_provider.call_args.args[1],
            self.session_dependency.session,
        )
        self.assertIs(
            self.authenticate_user_use_case_provider.call_args.args[1],
            self.session_dependency.session,
        )

    def test_authentication_errors_keep_existing_http_responses(self) -> None:
        self.login_use_case.execute.side_effect = AuthenticationError
        self.authenticate_user_use_case.execute.side_effect = AuthenticationError

        with TestClient(self.app) as client:
            login_response = client.post(
                "/auth/login",
                json={"email": "test@example.test", "password": "wrong"},
            )
            user_response = client.get(
                "/auth/me",
                headers={"Authorization": "Bearer invalid-token"},
            )
            missing_token_response = client.get("/auth/me")

        self.assertEqual(login_response.status_code, 401)
        self.assertEqual(
            login_response.json()["detail"],
            "Invalid email or password.",
        )
        self.assertEqual(user_response.status_code, 401)
        self.assertEqual(
            user_response.json()["detail"],
            "Invalid authentication credentials.",
        )
        self.assertEqual(missing_token_response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
