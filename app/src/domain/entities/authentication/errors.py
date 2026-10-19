class AuthenticationError(ValueError):
    pass


class InvalidCredentialsError(AuthenticationError):
    pass


class GlobalAdminGrantError(ValueError):
    pass
