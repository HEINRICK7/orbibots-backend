import punq
from pwdlib import PasswordHash

from app.src.infrastructure.authentication.password_hashing import (
    PasswordHashFactory,
)
from app.src.infrastructure.authentication.tokens import JwtAccessTokenProvider
from app.src.infrastructure.config.settings import Settings


def create_container(settings: Settings) -> punq.Container:
    container = punq.Container()
    container.register(Settings, instance=settings)
    container.register(JwtAccessTokenProvider, instance=JwtAccessTokenProvider(settings))
    container.register(PasswordHash, instance=PasswordHashFactory().create())
    return container
