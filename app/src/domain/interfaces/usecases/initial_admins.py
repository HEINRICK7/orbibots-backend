from typing import Protocol

from app.src.domain.dtos.initial_admins import InitialAdminAccount


class ProvisionInitialAdmins(Protocol):
    def execute(
        self,
        company_name: str,
        admins: tuple[InitialAdminAccount, InitialAdminAccount],
    ) -> None: ...
