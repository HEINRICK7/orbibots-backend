from collections.abc import Iterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.src.bootstrap import model_registry
from app.src.bootstrap.authentication import AuthenticationUseCaseProvider
from app.src.bootstrap.container import create_container
from app.src.infrastructure.authentication.bootstrap_admin import BootstrapAdmin
from app.src.infrastructure.config.settings import Settings
from app.src.presentation.api.authentication.router import AuthenticationRouter
from app.src.presentation.api.health_check.router import HealthCheckRouter


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    app_settings = settings or Settings.from_environment()
    model_registry.Base.metadata
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
        if (
            app_session_factory is not None
            and app_settings.bootstrap_admin_email
            and app_settings.bootstrap_admin_password
        ):
            with app_session_factory() as session:
                BootstrapAdmin().ensure(
                    session,
                    email=app_settings.bootstrap_admin_email,
                    password=app_settings.bootstrap_admin_password,
                    name=app_settings.bootstrap_admin_name,
                )
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

    application.include_router(HealthCheckRouter().router)

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
