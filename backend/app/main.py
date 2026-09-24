from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from .config import Settings, get_settings, LOCAL_FRONTEND_ORIGINS
from .database import create_database_engine, initialize_database
from .public_demo import check_demo_database_path, initialize_demo_data
from .routers.symptoms import router as symptoms_router
from .routers.environment import router as environment_router
from .routers.analysis import router as analysis_router
from .routers.daily_health import router as daily_health_router


def create_app(database_path: Path | None = None, *, settings: Settings | None = None) -> FastAPI:
    """Create the API; an explicit database path keeps tests isolated."""

    settings = settings if settings is not None else get_settings()
    database_path = settings.resolved_database_path(database_path)
    if settings.public_demo_mode:
        check_demo_database_path(database_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if settings.public_demo_mode:
            check_demo_database_path(database_path)
        engine = create_database_engine(database_path)
        try:
            initialize_database(engine)
            if settings.public_demo_mode:
                initialize_demo_data(engine)
            application.state.session_factory = sessionmaker(
                bind=engine, expire_on_commit=False
            )
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="AllerWatch", version="0.2.0", lifespan=lifespan)
    application.state.settings = settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[*LOCAL_FRONTEND_ORIGINS, *([settings.frontend_origin] if settings.frontend_origin else [])],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    application.include_router(symptoms_router)
    application.include_router(environment_router)
    application.include_router(analysis_router)
    application.include_router(daily_health_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        """Report that the local API is running."""
        return {"status": "ok"}

    @application.get("/config")
    def public_config() -> dict[str, bool]:
        """Expose only the mode needed for truthful frontend labelling, never paths."""
        return {"public_demo_mode": settings.public_demo_mode}

    return application


app = create_app()
