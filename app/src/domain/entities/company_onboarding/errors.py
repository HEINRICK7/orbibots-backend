class CompanyOnboardingError(Exception):
    """Base class for expected company onboarding failures."""


class InvalidCompanyOnboardingInputError(CompanyOnboardingError, ValueError):
    """The requested company onboarding data is invalid."""


class InvitationNotFoundError(CompanyOnboardingError):
    """No invitation matches the supplied public credential."""


class InvitationStateError(CompanyOnboardingError):
    """The invitation cannot be used in its current state."""


class InvitationExpiredError(InvitationStateError):
    """The invitation's one-time credential has expired."""


class InvitationRevokedError(InvitationNotFoundError):
    """The invitation was revoked by an administrator."""


class InvitationAlreadyAcceptedError(InvitationNotFoundError):
    """The invitation was already used to create its membership."""


class InvitationRateLimitError(CompanyOnboardingError):
    """The invitation operation is temporarily rate limited."""


class CompanyOnboardingConflictError(CompanyOnboardingError):
    """The requested onboarding operation conflicts with existing data."""
