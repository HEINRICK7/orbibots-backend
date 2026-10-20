from app.src.domain.dtos.company_onboarding import CompanyOnboardingSummary
from app.src.domain.entities.authentication.user import AuthenticatedUser
from app.src.domain.interfaces.gateways.company_onboarding import (
    CompanyOnboardingRepository,
)
from app.src.domain.interfaces.usecases.authentication import RequireGlobalAdmin
from app.src.domain.interfaces.usecases.company_onboarding import ListCompanyOnboarding


class ListCompanyOnboardingUseCase(ListCompanyOnboarding):
    def __init__(
        self,
        repository: CompanyOnboardingRepository,
        require_global_admin: RequireGlobalAdmin,
    ) -> None:
        self._repository = repository
        self._require_global_admin = require_global_admin

    def execute(
        self, actor: AuthenticatedUser
    ) -> tuple[CompanyOnboardingSummary, ...]:
        self._require_global_admin.execute(actor)
        return self._repository.list_company_onboarding()
