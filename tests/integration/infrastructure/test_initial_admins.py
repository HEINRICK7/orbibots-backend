import unittest
from unittest.mock import Mock

from pwdlib import PasswordHash
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.bootstrap.initial_admins import (
    InitialAdminAccount,
    InitialAdminProvisioner,
)
from src.bootstrap.model_registry import Base
from src.domain.authentication.global_role import GlobalRole
from src.infrastructure.authentication.models import UserRecord
from src.infrastructure.company_onboarding.models import (
    Company,
    Membership,
)
from src.infrastructure.config.settings import ConfigurationError


class InitialAdminProvisionerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.password_hash = Mock(spec=PasswordHash)
        self.password_hash.hash.side_effect = lambda password: f"argon2:{password}"
        self.admins = (
            InitialAdminAccount(
                name="Henrick",
                email="heinrickcostta@otimizanegocio.com",
                password="first-unique-strong-password-32",
            ),
            InitialAdminAccount(
                name="Jeremias",
                email="jeremiaspinheiro@furnassolucoes.com",
                password="second-unique-strong-password-42",
            ),
        )
        self.provisioner = InitialAdminProvisioner(
            self.session_factory,
            "otimizanegocio",
            self.admins,
            tuple(admin.email for admin in self.admins),
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_provisions_active_company_admins_with_hashed_passwords(self) -> None:
        self.provisioner.execute(self.password_hash)

        with self.session_factory() as session:
            company = session.scalar(select(Company))
            users = session.scalars(select(UserRecord).order_by(UserRecord.email)).all()
            memberships = session.scalars(select(Membership)).all()

        self.assertIsNotNone(company)
        assert company is not None
        self.assertEqual(company.name, "otimizanegocio")
        self.assertEqual(company.status, "ACTIVE")
        self.assertEqual(len(users), 2)
        self.assertEqual(
            {user.global_role for user in users},
            {GlobalRole.ADMIN.value},
        )
        self.assertEqual(
            {user.email for user in users},
            {admin.email for admin in self.admins},
        )
        self.assertEqual(
            {user.password_hash for user in users},
            {f"argon2:{admin.password}" for admin in self.admins},
        )
        self.assertEqual(len(memberships), 2)
        self.assertEqual({membership.role for membership in memberships}, {"COMPANY_ADMIN"})
        self.assertEqual({membership.status for membership in memberships}, {"ACTIVE"})
        self.assertEqual(
            {membership.company_id for membership in memberships},
            {company.id},
        )

    def test_repeated_provisioning_is_idempotent_and_does_not_reset_passwords(
        self,
    ) -> None:
        self.provisioner.execute(self.password_hash)
        initial_hash_calls = self.password_hash.hash.call_count

        self.provisioner.execute(self.password_hash)

        with self.session_factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Company)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(UserRecord)), 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(Membership)), 2)
        self.assertEqual(self.password_hash.hash.call_count, initial_hash_calls)

    def test_rejects_weak_passwords_before_writing_any_records(self) -> None:
        weak_admins = (
            self.admins[0],
            InitialAdminAccount(
                name=self.admins[1].name,
                email=self.admins[1].email,
                password="short",
            ),
        )
        provisioner = InitialAdminProvisioner(
            self.session_factory,
            "otimizanegocio",
            weak_admins,
            tuple(admin.email for admin in self.admins),
        )

        with self.assertRaises(ConfigurationError):
            provisioner.execute(self.password_hash)

        with self.session_factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Company)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(UserRecord)), 0)
        self.password_hash.hash.assert_not_called()

    def test_rejects_reused_passwords_before_writing_any_records(self) -> None:
        duplicate_password_admins = (
            self.admins[0],
            InitialAdminAccount(
                name=self.admins[1].name,
                email=self.admins[1].email,
                password=self.admins[0].password,
            ),
        )
        provisioner = InitialAdminProvisioner(
            self.session_factory,
            "otimizanegocio",
            duplicate_password_admins,
            tuple(admin.email for admin in self.admins),
        )

        with self.assertRaises(ConfigurationError):
            provisioner.execute(self.password_hash)

        with self.session_factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Company)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(UserRecord)), 0)
        self.password_hash.hash.assert_not_called()

    def test_rejects_admin_identities_that_do_not_match_the_allowlist(self) -> None:
        third_admin = InitialAdminAccount(
            name="Third Admin",
            email="third@example.test",
            password="a-different-strong-password-123",
        )
        provisioner = InitialAdminProvisioner(
            self.session_factory,
            "otimizanegocio",
            (self.admins[0], third_admin),
            tuple(admin.email for admin in self.admins),
        )

        with self.assertRaises(ConfigurationError):
            provisioner.execute(self.password_hash)

        with self.session_factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Company)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(UserRecord)), 0)
        self.password_hash.hash.assert_not_called()


if __name__ == "__main__":
    unittest.main()
