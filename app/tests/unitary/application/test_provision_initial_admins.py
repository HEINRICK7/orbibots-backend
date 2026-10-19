import unittest
from contextlib import nullcontext
from unittest.mock import Mock
from uuid import uuid4

from app.src.application.gateways.transactions import UnitOfWork
from app.src.application.usecases.provision_initial_admins import (
    InitialAdminProvisioningError,
    ProvisionInitialAdminsUseCase,
)
from app.src.domain.dtos.initial_admins import (
    InitialAdminAccount,
    ProvisioningCompany,
    ProvisioningUser,
)
from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.authentication.policies import GlobalAdminAllowlist
from app.src.domain.entities.authentication.status import UserStatus
from app.src.domain.entities.company_onboarding.status import CompanyStatus
from app.src.domain.interfaces.adapters.authentication import PasswordHasher
from app.src.domain.interfaces.gateways.initial_admins import (
    InitialAdminProvisioningGateway,
)
from app.src.domain.interfaces.usecases.authentication import GrantGlobalAdmin


class ProvisionInitialAdminsUseCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admins = (
            InitialAdminAccount(
                name="First Admin",
                email="first@example.test",
                password="first-strong-password-012345",
            ),
            InitialAdminAccount(
                name="Second Admin",
                email="second@example.test",
                password="second-strong-password-012345",
            ),
        )
        self.gateway = Mock(spec=InitialAdminProvisioningGateway)
        self.password_hasher = Mock(spec=PasswordHasher)
        self.grant_global_admin = Mock(spec=GrantGlobalAdmin)
        self.unit_of_work = Mock(spec=UnitOfWork)
        self.unit_of_work.transaction.return_value = nullcontext()
        self.allowlist = GlobalAdminAllowlist(
            tuple(admin.email for admin in self.admins)
        )
        self.use_case = ProvisionInitialAdminsUseCase(
            gateway=self.gateway,
            password_hasher=self.password_hasher,
            allowlist=self.allowlist,
            grant_global_admin=self.grant_global_admin,
            unit_of_work=self.unit_of_work,
        )

    def test_provisions_company_and_admin_memberships_through_ports(self) -> None:
        company = ProvisioningCompany(
            id=uuid4(),
            name="Example company",
            status=CompanyStatus.ACTIVE,
        )
        self.gateway.find_companies_by_name.return_value = ()
        self.gateway.create_company.return_value = company
        self.gateway.find_user_by_email.return_value = None
        self.gateway.create_user.side_effect = lambda name, email, encoded: ProvisioningUser(
            id=uuid4(),
            email=email,
            status=UserStatus.ACTIVE,
            has_password=bool(encoded),
        )
        self.gateway.find_active_membership.return_value = None
        self.password_hasher.hash.side_effect = lambda password: f"encoded:{password}"

        self.use_case.execute(" Example company ", self.admins)

        self.unit_of_work.transaction.assert_called_once_with()
        self.gateway.create_company.assert_called_once()
        self.assertEqual(self.gateway.create_user.call_count, 2)
        self.assertEqual(self.gateway.create_company_membership.call_count, 2)
        self.assertTrue(
            all(
                call.args[2] is CompanyRole.COMPANY_ADMIN
                for call in self.gateway.create_company_membership.call_args_list
            )
        )
        self.assertEqual(self.grant_global_admin.execute.call_count, 2)
        self.assertEqual(self.password_hasher.hash.call_count, 2)

    def test_rejects_invalid_configuration_before_opening_transaction(self) -> None:
        weak_admins = (
            self.admins[0],
            InitialAdminAccount(
                name=self.admins[1].name,
                email=self.admins[1].email,
                password="short",
            ),
        )

        with self.assertRaises(InitialAdminProvisioningError):
            self.use_case.execute("Example company", weak_admins)

        self.unit_of_work.transaction.assert_not_called()
        self.gateway.find_companies_by_name.assert_not_called()
        self.password_hasher.hash.assert_not_called()


if __name__ == "__main__":
    unittest.main()
