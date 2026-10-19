from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt import PyJWTError

from app.src.application.authentication.ports import IssuedAccessToken
from app.src.infrastructure.config.settings import ConfigurationError, Settings


class JwtAccessTokenProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def issue(self, user_id: UUID) -> IssuedAccessToken:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self._settings.access_token_expire_minutes)
        encoded = jwt.encode(
            {"sub": str(user_id), "iat": now, "exp": expires_at},
            self._secret(),
            algorithm=self._settings.jwt_algorithm,
        )
        return IssuedAccessToken(
            encoded=encoded,
            expires_in=self._settings.access_token_expire_minutes * 60,
        )

    def decode_subject(self, token: str) -> UUID:
        try:
            claims = jwt.decode(
                token,
                self._secret(),
                algorithms=[self._settings.jwt_algorithm],
                options={"require": ["sub", "iat", "exp"]},
            )
            return UUID(claims["sub"])
        except (PyJWTError, ValueError, TypeError) as exc:
            raise ValueError("Invalid access token.") from exc

    def _secret(self) -> str:
        secret = self._settings.jwt_secret_key
        if not secret:
            raise ConfigurationError("JWT_SECRET_KEY is required to use authentication.")
        return secret
