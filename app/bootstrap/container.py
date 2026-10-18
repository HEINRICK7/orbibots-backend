import punq
from pwdlib import PasswordHash

from app.contexts.authentication.infrastructure.password_hashing import (
    PasswordHashFactory,
)
from app.contexts.authentication.infrastructure.tokens import JwtAccessTokenProvider
from app.platform.config import Settings


def create_container(settings: Settings) -> punq.Container:
    container = punq.Container()
    container.register(Settings, instance=settings)
    container.register(JwtAccessTokenProvider, instance=JwtAccessTokenProvider(settings))
    container.register(PasswordHash, instance=PasswordHashFactory().create())
    return container
