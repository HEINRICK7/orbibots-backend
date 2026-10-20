from app.src.domain.entities.authentication.errors import GlobalAdminGrantError
from app.src.domain.entities.authentication.policies import (
    GlobalAdminAllowlist as _GlobalAdminAllowlist,
)
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.interfaces.gateways.authentication import GlobalAdminGrantRepository
from app.src.domain.interfaces.usecases.authentication import GrantGlobalAdmin


class GrantGlobalAdminUseCase(GrantGlobalAdmin):
    def __init__(
        self,
        repository: GlobalAdminGrantRepository,
        allowlist: _GlobalAdminAllowlist,
    ) -> None:
        self._repository = repository
        self._allowlist = allowlist

    def execute(self, email: str) -> AuthenticatedUser:
        allowed_email = self._allowlist.ensure_allowed(email)
        candidate = self._repository.get_global_admin_grant_candidate(allowed_email)
        if candidate is None or not candidate.is_active or not candidate.has_password:
            raise GlobalAdminGrantError(
                "Only an active user with a password hash can receive global ADMIN."
            )

        user = self._repository.grant_global_admin(allowed_email)
        if user is None:
            raise GlobalAdminGrantError(
                "Only an active user with a password hash can receive global ADMIN."
            )
        return user
