from collections.abc import Iterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap.authentication import AuthenticationUseCaseProvider
from app.bootstrap.container import create_container
from app.contexts.authentication.presentation.router import AuthenticationRouter
from app.platform.config import Settings


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    app_settings = settings or Settings.from_environment()
    engine: Engine | None = None
    app_session_factory = session_factory

    if app_session_factory is None and app_settings.database_url:
        engine = create_engine(app_settings.database_url, pool_pre_ping=True)
        app_session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> Iterator[None]:
        yield
        if engine is not None:
            engine.dispose()

    application = FastAPI(
        title="OrbiBots API",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    if app_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(app_settings.cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @application.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    application.state.container = create_container(app_settings)
    application.state.session_factory = app_session_factory
    authentication_use_cases = AuthenticationUseCaseProvider()
    application.include_router(
        AuthenticationRouter(
            authentication_use_cases.login,
            authentication_use_cases.authenticate_user,
        ).router,
        prefix="/auth",
        tags=["authentication"],
    )
    return application
