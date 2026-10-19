import unittest
from uuid import uuid4

from src.application.access.authorize_access import (
    RequireCompanyAdminUseCase,
    RequireGlobalAdminUseCase,
)
from src.domain.access.company_access import CompanyAccess
from src.domain.access.company_role import CompanyRole
from src.domain.access.errors import AccessDeniedError
from src.domain.authentication.global_role import GlobalRole
from src.domain.authentication.user import AuthenticatedUser


class AccessAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company_id = uuid4()
        self.company_admin = self._user(
            company_accesses=(
                CompanyAccess(
                    company_id=self.company_id,
                    company_name="Empresa A",
                    role=CompanyRole.COMPANY_ADMIN,
                    scope=None,
                ),
            )
        )

    def test_global_admin_use_case_allows_global_admin(self) -> None:
        admin = self._user(global_role=GlobalRole.ADMIN)

        self.assertIsNone(RequireGlobalAdminUseCase().execute(admin))

    def test_global_admin_use_case_rejects_company_admin(self) -> None:
        with self.assertRaises(AccessDeniedError):
            RequireGlobalAdminUseCase().execute(self.company_admin)

    def test_company_admin_use_case_requires_matching_company(self) -> None:
        self.assertIsNone(
            RequireCompanyAdminUseCase().execute(self.company_admin, self.company_id)
        )

        with self.assertRaises(AccessDeniedError):
            RequireCompanyAdminUseCase().execute(self.company_admin, uuid4())

    def test_company_admin_use_case_rejects_agent_editor(self) -> None:
        editor = self._user(
            company_accesses=(
                CompanyAccess(
                    company_id=self.company_id,
                    company_name="Empresa A",
                    role=CompanyRole.AGENT_EDITOR,
                    scope=None,
                ),
            )
        )

        with self.assertRaises(AccessDeniedError):
            RequireCompanyAdminUseCase().execute(editor, self.company_id)

    @staticmethod
    def _user(
        *,
        global_role: GlobalRole | None = None,
        company_accesses: tuple[CompanyAccess, ...] = (),
    ) -> AuthenticatedUser:
        return AuthenticatedUser(
            id=uuid4(),
            name="Test User",
            email="user@example.test",
            is_active=True,
            global_role=global_role,
            company_accesses=company_accesses,
        )


if __name__ == "__main__":
    unittest.main()
