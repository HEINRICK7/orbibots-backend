from app.src.domain.entities.authentication.policies import GlobalAdminAllowlist
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.interfaces.gateways.authentication import GlobalAdminGrantRepository
from app.src.domain.interfaces.usecases.authentication import GrantGlobalAdmin


class GrantGlobalAdminUseCase(GrantGlobalAdmin):
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
