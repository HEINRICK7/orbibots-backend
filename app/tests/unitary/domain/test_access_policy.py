import unittest
from uuid import uuid4

from app.src.domain.entities.access.company_access import CompanyAccess
from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.access.policy import AccessPolicy
from app.src.domain.entities.authentication.global_role import GlobalRole
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.entities.company_onboarding.membership_scope import MembershipScope


class AccessPolicyTests(unittest.TestCase):
    def test_only_active_global_admin_enters_global_area(self) -> None:
        admin = self._user(global_role=GlobalRole.ADMIN)
        regular_user = self._user()
        inactive_admin = self._user(is_active=False, global_role=GlobalRole.ADMIN)

        self.assertTrue(AccessPolicy.can_access_global_admin_area(admin))
        self.assertFalse(AccessPolicy.can_access_global_admin_area(regular_user))
        self.assertFalse(AccessPolicy.can_access_global_admin_area(inactive_admin))

    def test_company_admin_can_access_only_the_company_with_active_grant(self) -> None:
        company_id = uuid4()
        other_company_id = uuid4()
        company_admin = self._user(
            company_accesses=(
                CompanyAccess(
                    company_id=company_id,
                    company_name="Empresa A",
                    role=CompanyRole.COMPANY_ADMIN,
                    scope=MembershipScope.COMPANY,
                ),
            )
        )
        editor = self._user(
            company_accesses=(
                CompanyAccess(
                    company_id=company_id,
                    company_name="Empresa A",
                    role=CompanyRole.AGENT_EDITOR,
                    scope=MembershipScope.ASSIGNED_AGENTS,
                ),
            )
        )
        inactive_company_admin = self._user(
            is_active=False,
            company_accesses=company_admin.company_accesses,
        )

        self.assertTrue(AccessPolicy.can_access_company_area(company_admin, company_id))
        self.assertFalse(
            AccessPolicy.can_access_company_area(company_admin, other_company_id)
        )
        self.assertFalse(AccessPolicy.can_access_company_area(editor, company_id))
        self.assertFalse(
            AccessPolicy.can_access_company_area(inactive_company_admin, company_id)
        )

    @staticmethod
    def _user(
        *,
        is_active: bool = True,
        global_role: GlobalRole | None = None,
        company_accesses: tuple[CompanyAccess, ...] = (),
    ) -> AuthenticatedUser:
        return AuthenticatedUser(
            id=uuid4(),
            name="Test User",
            email="user@example.test",
            is_active=is_active,
            global_role=global_role,
            company_accesses=company_accesses,
        )


if __name__ == "__main__":
    unittest.main()
