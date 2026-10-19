import unittest
from unittest.mock import Mock
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.application.authentication.ports import IssuedAccessToken
from src.application.authentication.use_cases.authenticate_user import (
    AuthenticateUserUseCase,
)
from src.application.authentication.use_cases.login import LoginUseCase
from src.domain.authentication.errors import AuthenticationError
from src.domain.authentication.global_role import GlobalRole
from src.domain.authentication.user import AuthenticatedUser
from src.presentation.api.authentication.dependencies import (
    database_session_dependency,
)
from src.presentation.api.authentication.router import AuthenticationRouter


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
        self.authentication_router = AuthenticationRouter(
            self.login_use_case_provider,
            self.authenticate_user_use_case_provider,
        )
        self.app.include_router(self.authentication_router.router, prefix="/auth")
        self.app.add_api_route(
            "/global",
            lambda: {"status": "ok"},
            dependencies=[
                Depends(self.authentication_router.require_global_admin)
            ],
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

    def test_login_rejects_payloads_outside_the_swagger_contract(self) -> None:
        self.login_use_case.execute.return_value = IssuedAccessToken(
            encoded="signed-token",
            expires_in=60,
        )
        rejected = [
            {},
            {"email": "ab", "password": "x"},
            {"email": "a" * 321, "password": "x"},
            {"email": "abc", "password": ""},
            {"email": "abc", "password": "x" * 1025},
            {"email": "abc"},
            {"password": "x"},
            {"email": 1, "password": "x"},
            {"email": "abc", "password": None},
        ]

        with TestClient(self.app) as client:
            responses = [client.post("/auth/login", json=payload) for payload in rejected]
            accepted = [
                client.post("/auth/login", json={"email": "abc", "password": "x"}),
                client.post(
                    "/auth/login",
                    json={"email": "a" * 320, "password": "x" * 1024},
                ),
            ]

        self.assertEqual([response.status_code for response in responses], [422] * len(rejected))
        self.assertEqual([response.status_code for response in accepted], [200, 200])
        self.assertEqual(self.login_use_case.execute.call_count, 2)
        self.login_use_case.execute.assert_any_call("abc", "x")
        self.login_use_case.execute.assert_any_call("a" * 320, "x" * 1024)

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

    def test_global_admin_dependency_allows_admin_and_denies_regular_users(self) -> None:
        admin = AuthenticatedUser(
            id=uuid4(),
            name="Global Admin",
            email="admin@example.test",
            is_active=True,
            global_role=GlobalRole.ADMIN,
        )
        regular_user = AuthenticatedUser(
            id=uuid4(),
            name="Regular User",
            email="user@example.test",
            is_active=True,
        )
        self.authenticate_user_use_case.execute.side_effect = [admin, regular_user]

        with TestClient(self.app) as client:
            admin_response = client.get(
                "/global", headers={"Authorization": "Bearer valid-token"}
            )
            regular_response = client.get(
                "/global", headers={"Authorization": "Bearer valid-token"}
            )
            missing_token_response = client.get("/global")

        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(regular_response.status_code, 403)
        self.assertEqual(missing_token_response.status_code, 401)

    def test_global_role_changes_take_effect_without_renewing_the_token(self) -> None:
        admin = AuthenticatedUser(
            id=uuid4(),
            name="Global Admin",
            email="admin@example.test",
            is_active=True,
            global_role=GlobalRole.ADMIN,
        )
        regular_user = AuthenticatedUser(
            id=admin.id,
            name=admin.name,
            email=admin.email,
            is_active=True,
        )
        self.authenticate_user_use_case.execute.side_effect = [admin, regular_user]

        with TestClient(self.app) as client:
            headers = {"Authorization": "Bearer unchanged-token"}
            initially_allowed = client.get("/global", headers=headers)
            after_role_removal = client.get("/global", headers=headers)

        self.assertEqual(initially_allowed.status_code, 200)
        self.assertEqual(after_role_removal.status_code, 403)
        self.assertEqual(
            self.authenticate_user_use_case.execute.call_args_list[0].args[0],
            "unchanged-token",
        )
        self.assertEqual(
            self.authenticate_user_use_case.execute.call_args_list[1].args[0],
            "unchanged-token",
        )

    def test_global_admin_dependency_preserves_unauthorized_responses(self) -> None:
        self.authenticate_user_use_case.execute.side_effect = AuthenticationError

        with TestClient(self.app) as client:
            response = client.get(
                "/global", headers={"Authorization": "Bearer invalid-token"}
            )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
