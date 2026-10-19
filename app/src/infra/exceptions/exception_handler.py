from dataclasses import dataclass
from typing import Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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
from app.src.infra.setup.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExceptionMapping:
    code: ErrorCode
    status_code: int
    safe_detail: str
    headers: Mapping[str, str] | None = None


class ExceptionHandler:
    """Map application failures to the existing HTTP error response shape."""

    _mappings: dict[type[Exception], ExceptionMapping] = {
        InvalidCredentialsError: ExceptionMapping(
            ErrorCode.INVALID_CREDENTIALS,
            401,
            "Invalid email or password.",
        ),
        AuthenticationRequiredError: ExceptionMapping(
            ErrorCode.AUTHENTICATION_REQUIRED,
            401,
            "Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ),
        AuthenticationError: ExceptionMapping(
            ErrorCode.AUTHENTICATION_REQUIRED,
            401,
            "Invalid authentication credentials.",
        ),
        AccessDeniedError: ExceptionMapping(
            ErrorCode.ACCESS_DENIED,
            403,
            "Insufficient permissions.",
        ),
        DatabaseUnavailableError: ExceptionMapping(
            ErrorCode.DATABASE_UNAVAILABLE,
            503,
            "Database is not configured.",
        ),
    }
    _unexpected = ExceptionMapping(
        ErrorCode.INTERNAL_ERROR,
        500,
        "An unexpected error occurred.",
    )

    def register(self, application: FastAPI) -> None:
        for exception_type in self._mappings:
            application.add_exception_handler(exception_type, self.handle)
        application.add_exception_handler(Exception, self.handle)

    async def handle(self, request: Request, exc: Exception) -> JSONResponse:
        mapping = self._mapping_for(exc)
        if mapping.code is ErrorCode.INTERNAL_ERROR:
            logger.error(
                "Unhandled request failure for %s",
                request.url.path,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        else:
            logger.info(
                "Request rejected with %s for %s",
                mapping.code.value,
                request.url.path,
            )

        return JSONResponse(
            status_code=mapping.status_code,
            content={"detail": mapping.safe_detail},
            headers=dict(mapping.headers or {}),
        )

    @classmethod
    def _mapping_for(cls, exc: Exception) -> ExceptionMapping:
        for exception_type in type(exc).__mro__:
            mapping = cls._mappings.get(exception_type)
            if mapping is not None:
                return mapping
        return cls._unexpected
