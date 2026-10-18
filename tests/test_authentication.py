import unittest
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.bootstrap.model_registry import Base
from app.bootstrap.startup import create_app
from app.contexts.authentication.application.use_cases.login import LoginUseCase
from app.contexts.authentication.domain.errors import AuthenticationError
from app.contexts.authentication.infrastructure.models import UserRecord
from app.contexts.authentication.infrastructure.password_hashing import (
    PwdlibPasswordVerifier,
)
from app.contexts.authentication.infrastructure.repository import (
    SqlAlchemyUserAuthenticationRepository,
)
from app.contexts.authentication.infrastructure.tokens import JwtAccessTokenProvider
from app.contexts.authentication.infrastructure.bootstrap_admin import BootstrapAdmin
from app.platform.config import ConfigurationError, Settings


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.session_factory = sessionmaker(
            bind=cls.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        cls.settings = Settings(
            app_env="test",
            jwt_secret_key="test-only-secret-with-at-least-32-bytes",
            access_token_expire_minutes=5,
        )
        cls.password_hash = PasswordHash.recommended()
        cls.user_id = None
        with cls.session_factory() as session:
            user = UserRecord(
                name="Test User",
                email="test@example.test",
                password_hash=cls.password_hash.hash("correct horse battery staple"),
                status="ACTIVE",
            )
            session.add(user)
            session.commit()
            cls.user_id = user.id

    @classmethod
    def tearDownClass(cls) -> None:
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def create_client(self) -> TestClient:
        return TestClient(
            create_app(
                self.settings,
                session_factory=self.session_factory,
            )
        )

    def test_login_returns_a_signed_bearer_token(self) -> None:
        with self.create_client() as client:
            response = client.post(
                "/auth/login",
                json={
                    "email": "TEST@example.test",
                    "password": "correct horse battery staple",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["token_type"], "bearer")
        self.assertEqual(body["expires_in"], 300)
        claims = jwt.decode(
            body["access_token"],
            self.settings.jwt_secret_key,
            algorithms=["HS256"],
        )
        self.assertEqual(claims["sub"], str(self.user_id))
        self.assertNotIn("password", claims)
        self.assertNotIn("password_hash", claims)

    def test_http_paths_remain_compatible(self) -> None:
        with self.create_client() as client:
            response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()["paths"]),
            {"/auth/login", "/auth/me", "/health"},
        )

    def test_asgi_entry_point_is_inside_app_package(self) -> None:
        from app.main import app

        self.assertIsInstance(app, FastAPI)

    def test_invalid_credentials_are_generic_and_do_not_issue_tokens(self) -> None:
        with self.create_client() as client:
            response = client.post(
                "/auth/login",
                json={"email": "test@example.test", "password": "incorrect"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid email or password.")
        self.assertNotIn("access_token", response.json())

    def test_user_without_password_hash_cannot_log_in(self) -> None:
        with self.session_factory() as session:
            session.add(
                UserRecord(
                    name="Unprovisioned",
                    email="new@example.test",
                    status="ACTIVE",
                )
            )
            session.commit()

        with self.create_client() as client:
            response = client.post(
                "/auth/login",
                json={"email": "new@example.test", "password": "any-password"},
            )

        self.assertEqual(response.status_code, 401)

    def test_inactive_user_cannot_log_in_or_authenticate(self) -> None:
        with self.session_factory() as session:
            user = session.get(UserRecord, self.user_id)
            assert user is not None
            user.status = "SUSPENDED"
            session.commit()

        with self.create_client() as client:
            login_response = client.post(
                "/auth/login",
                json={
                    "email": "test@example.test",
                    "password": "correct horse battery staple",
                },
            )
            protected_response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {self._valid_token()}"},
            )

        self.assertEqual(login_response.status_code, 401)
        self.assertEqual(protected_response.status_code, 401)
        with self.session_factory() as session:
            user = session.get(UserRecord, self.user_id)
            assert user is not None
            user.status = "ACTIVE"
            session.commit()

    def test_bearer_token_authenticates_active_user(self) -> None:
        with self.create_client() as client:
            response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {self._valid_token()}"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "test@example.test")
        self.assertNotIn("password_hash", response.json())

    def test_missing_malformed_and_expired_tokens_are_rejected(self) -> None:
        expired_token = jwt.encode(
            {
                "sub": str(self.user_id),
                "iat": datetime.now(timezone.utc) - timedelta(minutes=10),
                "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
            },
            self.settings.jwt_secret_key,
            algorithm="HS256",
        )
        with self.create_client() as client:
            responses = [
                client.get("/auth/me"),
                client.get(
                    "/auth/me",
                    headers={"Authorization": "Bearer not-a-jwt"},
                ),
                client.get(
                    "/auth/me",
                    headers={"Authorization": f"Bearer {expired_token}"},
                ),
            ]

        self.assertEqual([response.status_code for response in responses], [401, 401, 401])

    def test_bootstrap_admin_is_created_once(self) -> None:
        with self.session_factory() as session:
            admin = BootstrapAdmin()
            admin.ensure(
                session,
                email="Admin@Example.test",
                password="correct horse battery staple",
                name="Administrador",
            )
            admin.ensure(
                session,
                email="admin@example.test",
                password="another-password",
                name="Outro",
            )
            stored = session.scalar(
                select(UserRecord).where(UserRecord.email == "admin@example.test")
            )

        self.assertIsNotNone(stored)
        self.assertEqual(stored.name, "Administrador")
        self.assertTrue(
            PwdlibPasswordVerifier(PasswordHash.recommended()).verify(
                "correct horse battery staple",
                stored.password_hash,
            )
        )

    def test_production_configuration_requires_database_and_signing_secret(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings(app_env="production")
        with self.assertRaises(ConfigurationError):
            Settings(app_env="staging")

    def test_swagger_and_health_are_public(self) -> None:
        with self.create_client() as client:
            health = client.get("/health")
            swagger = client.get("/docs")
            openapi = client.get("/openapi.json")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "ok"})
        self.assertEqual(swagger.status_code, 200)
        self.assertIn("/auth/login", openapi.json()["paths"])

    def test_application_containers_are_isolated_per_instance(self) -> None:
        first_app = create_app(self.settings, session_factory=self.session_factory)
        second_app = create_app(self.settings, session_factory=self.session_factory)

        self.assertIsNot(first_app.state.container, second_app.state.container)
        self.assertIsInstance(
            first_app.state.container.resolve(JwtAccessTokenProvider),
            JwtAccessTokenProvider,
        )

    def test_database_sessions_are_created_per_dependency_use(self) -> None:
        app = create_app(self.settings, session_factory=self.session_factory)
        request = type("Request", (), {"app": app})()
        from app.contexts.authentication.presentation.dependencies import (
            database_session_dependency,
        )

        first_session = next(database_session_dependency(request))
        second_session = next(database_session_dependency(request))
        try:
            self.assertIsInstance(first_session, Session)
            self.assertIsNot(first_session, second_session)
        finally:
            first_session.close()
            second_session.close()

    def test_missing_database_configuration_returns_service_unavailable(self) -> None:
        with TestClient(create_app(Settings(app_env="test"))) as client:
            response = client.post(
                "/auth/login",
                json={"email": "test@example.test", "password": "password"},
            )

        self.assertEqual(response.status_code, 503)

    def test_service_rejects_invalid_stored_hash(self) -> None:
        with self.session_factory() as session:
            user = UserRecord(
                name="Corrupt",
                email="corrupt@example.test",
                password_hash="unknown$hash$format",
                status="ACTIVE",
            )
            session.add(user)
            session.commit()
            container = create_app(
                self.settings, session_factory=self.session_factory
            ).state.container
            use_case = LoginUseCase(
                SqlAlchemyUserAuthenticationRepository(session),
                PwdlibPasswordVerifier(container.resolve(PasswordHash)),
                container.resolve(JwtAccessTokenProvider),
            )
            with self.assertRaises(AuthenticationError):
                use_case.execute(user.email, "password")

    def _valid_token(self) -> str:
        return JwtAccessTokenProvider(self.settings).issue(self.user_id).encoded


if __name__ == "__main__":
    unittest.main()
