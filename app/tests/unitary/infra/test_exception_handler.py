import unittest

from app.src.domain.entities.access.errors import AccessDeniedError
from app.src.domain.entities.authentication.errors import (
    AuthenticationError,
    InvalidCredentialsError,
)
from app.src.infra.exceptions.error_code import ErrorCode
from app.src.infra.exceptions.errors import (
    AuthenticationRequiredError,
    DatabaseUnavailableError,
)
from app.src.infra.exceptions.exception_handler import ExceptionHandler


class ExceptionHandlerTests(unittest.TestCase):
    def test_known_failures_map_to_stable_codes_and_http_statuses(self) -> None:
        cases = (
            (InvalidCredentialsError(), ErrorCode.INVALID_CREDENTIALS, 401),
            (AuthenticationError(), ErrorCode.AUTHENTICATION_REQUIRED, 401),
            (AuthenticationRequiredError(), ErrorCode.AUTHENTICATION_REQUIRED, 401),
            (AccessDeniedError("denied"), ErrorCode.ACCESS_DENIED, 403),
            (DatabaseUnavailableError(), ErrorCode.DATABASE_UNAVAILABLE, 503),
        )

        for error, expected_code, expected_status in cases:
            with self.subTest(error=type(error).__name__):
                mapping = ExceptionHandler._mapping_for(error)
                self.assertIs(mapping.code, expected_code)
                self.assertEqual(mapping.status_code, expected_status)

    def test_unknown_failures_map_to_safe_internal_error(self) -> None:
        mapping = ExceptionHandler._mapping_for(RuntimeError("private detail"))

        self.assertIs(mapping.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(mapping.status_code, 500)
        self.assertEqual(mapping.safe_detail, "An unexpected error occurred.")


if __name__ == "__main__":
    unittest.main()
