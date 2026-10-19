import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def load_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    database_url: str | None = None
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_origins: tuple[str, ...] = ()
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_name: str = "Administrador"
    global_admin_allowed_emails: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.app_env not in {"development", "test", "staging", "production"}:
            raise ConfigurationError(
                "APP_ENV must be development, test, staging, or production."
            )
        if self.jwt_algorithm != "HS256":
            raise ConfigurationError("JWT_ALGORITHM must be HS256.")
        if not 1 <= self.access_token_expire_minutes <= 1440:
            raise ConfigurationError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440.")
        email = (self.bootstrap_admin_email or "").strip()
        password = self.bootstrap_admin_password or ""
        if bool(email) != bool(password):
            raise ConfigurationError(
                "BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD must be set together."
            )
        if password and len(password) < 8:
            raise ConfigurationError(
                "BOOTSTRAP_ADMIN_PASSWORD must contain at least 8 characters."
            )
        if self.app_env in {"staging", "production"}:
            if not self.database_url:
                raise ConfigurationError("DATABASE_URL is required in staging and production.")
            if not self.jwt_secret_key or len(self.jwt_secret_key) < 32:
                raise ConfigurationError(
                    "JWT_SECRET_KEY must contain at least 32 characters in staging and production."
                )

    @classmethod
    def from_environment(cls) -> "Settings":
        load_environment()
        database_url = os.getenv("DATABASE_URL")
        jwt_secret_key = os.getenv("JWT_SECRET_KEY")
        global_admin_allowed_emails = os.getenv("GLOBAL_ADMIN_ALLOWED_EMAILS")
        return cls(
            app_env=os.getenv("APP_ENV", "development").lower(),
            database_url=database_url or None,
            jwt_secret_key=jwt_secret_key or None,
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            access_token_expire_minutes=int(
                os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
            ),
            cors_origins=tuple(
                origin.strip()
                for origin in os.getenv("CORS_ORIGINS", "").split(",")
                if origin.strip()
            ),
            bootstrap_admin_email=os.getenv("BOOTSTRAP_ADMIN_EMAIL") or None,
            bootstrap_admin_password=os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or None,
            bootstrap_admin_name=os.getenv("BOOTSTRAP_ADMIN_NAME", "Administrador"),
            global_admin_allowed_emails=(
                tuple(
                    email.strip()
                    for email in global_admin_allowed_emails.split(",")
                )
                if global_admin_allowed_emails
                else ()
            ),
        )
