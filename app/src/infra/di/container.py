from collections.abc import Mapping
from typing import Any

import punq
from pwdlib import PasswordHash

from app.src.application.usecases.authorize_access import (
    RequireCompanyAdminUseCase,
    RequireGlobalAdminUseCase,
)
from app.src.domain.interfaces.adapters.authentication import (
    AccessTokenProvider,
    PasswordHasher,
    PasswordVerifier,
)
from app.src.infra.adapters.authentication.password_hashing import (
    PasswordHashFactory,
    PwdlibPasswordHasher,
    PwdlibPasswordVerifier,
)
from app.src.infra.adapters.authentication.tokens import JwtAccessTokenProvider
from app.src.infra.di.authentication import AuthenticationUseCaseProvider
from app.src.infra.setup.settings import Settings


def create_container(
    settings: Settings,
    *,
    overrides: Mapping[type[Any], object] | None = None,
) -> punq.Container:
    """Build the application graph; tests can replace boundary contracts."""
    container = punq.Container()
    password_hash = PasswordHashFactory().create()
    access_tokens = JwtAccessTokenProvider(settings)
    container.register(Settings, instance=settings)
    container.register(RequireCompanyAdminUseCase)
    container.register(RequireGlobalAdminUseCase)
    container.register(PasswordHash, instance=password_hash)
    container.register(
        PasswordVerifier,
        instance=PwdlibPasswordVerifier(password_hash),
    )
    container.register(
        PasswordHasher,
        instance=PwdlibPasswordHasher(password_hash),
    )
    container.register(JwtAccessTokenProvider, instance=access_tokens)
    container.register(AccessTokenProvider, instance=access_tokens)
    container.register(
        AuthenticationUseCaseProvider,
        instance=AuthenticationUseCaseProvider(container),
    )

    for contract, dependency in (overrides or {}).items():
        container.register(contract, instance=dependency)

    return container
