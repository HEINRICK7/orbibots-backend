from collections.abc import Iterator
import asyncio
from contextlib import suppress
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.src.application.usecases.authorize_access import (
    RequireCompanyAdminUseCase,
    RequireGlobalAdminUseCase,
)
from app.src.infra.di.authentication import AuthenticationUseCaseProvider
from app.src.infra.di.container import create_container
from app.src.infra.exceptions.exception_handler import ExceptionHandler
from app.src.infra.di.bootstrap_admin import build_bootstrap_admin
from app.src.infra.di.company_onboarding import build_send_invitation_email_use_case
from app.src.infra.setup import model_registry
from app.src.infra.setup.logging_config import configure_logging, get_logger
from app.src.infra.setup.settings import Settings
from app.src.infra.controllers.authentication.router import AuthenticationRouter
from app.src.infra.controllers.health_check.router import HealthCheckRouter


logger = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    configure_logging()
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
                build_bootstrap_admin(
                    session,
                    app_settings.global_admin_allowed_emails,
                ).ensure(
                    email=app_settings.bootstrap_admin_email,
                    password=app_settings.bootstrap_admin_password,
                    name=app_settings.bootstrap_admin_name,
                )
        outbox_worker = None
        if app_session_factory is not None and app_settings.invitation_email_configured:
            outbox_worker = asyncio.create_task(
                _dispatch_invitation_outbox(app_session_factory, app_settings)
            )
        yield
        if outbox_worker is not None:
            outbox_worker.cancel()
            with suppress(asyncio.CancelledError):
                await outbox_worker
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

    container = create_container(app_settings)
    application.state.container = container
    application.state.session_factory = app_session_factory
    application.state.invitation_email_dispatcher_provider = (
        (lambda session: build_send_invitation_email_use_case(session, app_settings))
        if app_settings.invitation_email_configured
        else None
    )
    authentication_use_cases = container.resolve(AuthenticationUseCaseProvider)
    application.include_router(
        AuthenticationRouter(
            authentication_use_cases.login,
            authentication_use_cases.authenticate_user,
            container.resolve(RequireGlobalAdminUseCase),
            container.resolve(RequireCompanyAdminUseCase),
        ).router,
        prefix="/auth",
        tags=["authentication"],
    )
    ExceptionHandler().register(application)
    return application


async def _dispatch_invitation_outbox(
    session_factory: sessionmaker[Session], settings: Settings
) -> None:
    while True:
        try:
            def dispatch_batch() -> None:
                with session_factory() as session:
                    build_send_invitation_email_use_case(
                        session, settings
                    ).dispatch_pending()

            await asyncio.to_thread(dispatch_batch)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "Invitation outbox batch failed (%s)",
                type(exc).__name__,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        await asyncio.sleep(5)
