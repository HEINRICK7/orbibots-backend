class AuthenticationRequiredError(Exception):
    """The request did not include an authentication credential."""


class DatabaseUnavailableError(Exception):
    """The application cannot serve requests without a database session."""


class ConfigurationError(RuntimeError):
    """Runtime configuration is missing or invalid."""
