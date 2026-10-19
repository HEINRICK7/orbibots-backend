from app.src.application.authentication.ports import GlobalAdminGrantRepository
from app.src.domain.authentication.policies import GlobalAdminAllowlist
from app.src.domain.authentication.user import AuthenticatedUser


class GrantGlobalAdminUseCase:
    def __init__(
        self,
        repository: GlobalAdminGrantRepository,
        allowlist: GlobalAdminAllowlist,
    ) -> None:
        self._repository = repository
        self._allowlist = allowlist

    def execute(self, email: str) -> AuthenticatedUser:
        allowed_email = self._allowlist.ensure_allowed(email)
        return self._repository.grant_global_admin(allowed_email)


__all__ = ["GlobalAdminAllowlist", "GrantGlobalAdminUseCase"]
