import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.engine import make_url

from app.contexts.authentication.infrastructure.models import UserRecord
from app.contexts.company_onboarding.infrastructure.models import (
    Company,
    Invitation,
    Membership,
)
from app.platform.config import load_environment


ONBOARDING_TABLES = {
    "audit_events",
    "companies",
    "invitations",
    "memberships",
    "users",
}


class PostgresSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_environment()
        cls.database_url = os.getenv("DATABASE_URL")
        if not cls.database_url:
            raise unittest.SkipTest(
                "DATABASE_URL is required. Copy .env.example to .env and configure it."
            )
        database_name = make_url(cls.database_url).database
        if database_name is None or not database_name.endswith("_test"):
            raise RuntimeError(
                "Integration tests require a disposable PostgreSQL database whose "
                "name ends with '_test'."
            )

        cls.alembic_config = Config("alembic.ini")
        cls.alembic_config.set_main_option(
            "sqlalchemy.url", cls.database_url.replace("%", "%%")
        )
        cls.engine = create_engine(
            cls.database_url, connect_args={"connect_timeout": 3}
        )
        try:
            with cls.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            command.upgrade(cls.alembic_config, "head")
        except SQLAlchemyError as exc:
            cls.engine.dispose()
            raise unittest.SkipTest(
                "PostgreSQL is unavailable. Start the test database with "
                "'docker compose up -d --wait postgres' and set DATABASE_URL."
            ) from exc

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "engine"):
            cls.engine.dispose()

    def test_1_migration_creates_schema_constraints_and_enum(self) -> None:
        inspector = inspect(self.engine)
        self.assertTrue(ONBOARDING_TABLES.issubset(inspector.get_table_names()))

        membership_columns = {
            column["name"]: column for column in inspector.get_columns("memberships")
        }
        self.assertEqual(membership_columns["scope"]["type"].name, "membership_scope")

        index_names = {
            index["name"]
            for table in ONBOARDING_TABLES
            for index in inspector.get_indexes(table)
        }
        self.assertIn("uq_users_email_lower", index_names)
        self.assertIn("uq_memberships_active_user_company", index_names)
        self.assertIn("uq_invitations_company_email_lower", index_names)

        membership_foreign_keys = {
            tuple(foreign_key["constrained_columns"]): foreign_key["referred_table"]
            for foreign_key in inspector.get_foreign_keys("memberships")
        }
        self.assertEqual(membership_foreign_keys[("company_id",)], "companies")
        self.assertEqual(membership_foreign_keys[("user_id",)], "users")
        self.assertEqual(
            inspect(Company).relationships["memberships"].mapper.class_,
            Membership,
        )
        self.assertEqual(
            inspect(Membership).relationships["user"].mapper.class_,
            UserRecord,
        )
        self.assertEqual(
            inspect(Company).relationships["invitations"].mapper.class_,
            Invitation,
        )

        with self.engine.connect() as connection:
            enum_values = connection.execute(
                text(
                    """
                    SELECT enumlabel
                    FROM pg_enum
                    JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
                    WHERE pg_type.typname = 'membership_scope'
                    ORDER BY enumsortorder
                    """
                )
            ).scalars().all()
        self.assertEqual(enum_values, ["COMPANY", "ASSIGNED_AGENTS"])

    def test_2_postgres_rejects_invalid_foreign_keys_and_duplicate_active_memberships(
        self,
    ) -> None:
        company_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO companies (id, name) VALUES (:id, 'Test Company')"
                ),
                {"id": company_id},
            )
            connection.execute(
                text(
                    "INSERT INTO users (id, name, email) "
                    "VALUES (:id, 'Test User', :email)"
                ),
                {"id": user_id, "email": f"{user_id}@example.test"},
            )

            with self.assertRaises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO users (id, name, email) "
                            "VALUES (:id, 'Duplicate User', :email)"
                        ),
                        {
                            "id": uuid.uuid4(),
                            "email": f"{user_id}@EXAMPLE.TEST",
                        },
                    )

            with self.assertRaises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            """
                            INSERT INTO memberships
                                (id, company_id, user_id, role, status)
                            VALUES (:id, :company_id, :user_id, 'COMPANY_ADMIN', 'ACTIVE')
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "company_id": uuid.uuid4(),
                            "user_id": user_id,
                        },
                    )

            membership_id = uuid.uuid4()
            connection.execute(
                text(
                    """
                    INSERT INTO memberships
                        (id, company_id, user_id, role, scope, status)
                    VALUES (:id, :company_id, :user_id, 'COMPANY_ADMIN', 'COMPANY', 'ACTIVE')
                    """
                ),
                {
                    "id": membership_id,
                    "company_id": company_id,
                    "user_id": user_id,
                },
            )

            with self.assertRaises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            """
                            INSERT INTO memberships
                                (id, company_id, user_id, role, scope, status)
                            VALUES (:id, :company_id, :user_id, 'AGENT_EDITOR',
                                    'ASSIGNED_AGENTS', 'ACTIVE')
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "company_id": company_id,
                            "user_id": user_id,
                        },
                    )

            with self.assertRaises(DataError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            """
                            INSERT INTO memberships
                                (id, company_id, user_id, role, scope, status)
                            VALUES (:id, :company_id, :user_id, 'AGENT_EDITOR',
                                    'NOT_A_SCOPE', 'SUSPENDED')
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "company_id": company_id,
                            "user_id": user_id,
                        },
                    )

            connection.execute(
                text(
                    "INSERT INTO invitations "
                    "(id, company_id, invited_name, email, intended_role, token_hash, expires_at) "
                    "VALUES (:id, :company_id, 'Invitee', :email, 'AGENT_EDITOR', :token, :expires_at)"
                ),
                {
                    "id": uuid.uuid4(),
                    "company_id": company_id,
                    "email": f"invite-{user_id}@example.test",
                    "token": uuid.uuid4().hex,
                    "expires_at": now + timedelta(days=1),
                },
            )

            with self.assertRaises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO invitations "
                            "(id, company_id, invited_name, email, intended_role, token_hash, expires_at) "
                            "VALUES (:id, :company_id, 'Duplicate Invitee', :email, "
                            "'AGENT_EDITOR', :token, :expires_at)"
                        ),
                        {
                            "id": uuid.uuid4(),
                            "company_id": company_id,
                            "email": f"INVITE-{user_id}@EXAMPLE.TEST",
                            "token": uuid.uuid4().hex,
                            "expires_at": now + timedelta(days=1),
                        },
                    )

    def test_3_migration_downgrade_and_upgrade_round_trip(self) -> None:
        command.downgrade(self.alembic_config, "base")
        inspector = inspect(self.engine)
        self.assertFalse(ONBOARDING_TABLES.intersection(inspector.get_table_names()))

        with self.engine.connect() as connection:
            enum_count = connection.execute(
                text(
                    "SELECT count(*) FROM pg_type WHERE typname = 'membership_scope'"
                )
            ).scalar_one()
        self.assertEqual(enum_count, 0)

        command.upgrade(self.alembic_config, "head")
        self.assertTrue(
            ONBOARDING_TABLES.issubset(inspect(self.engine).get_table_names())
        )


if __name__ == "__main__":
    unittest.main()
