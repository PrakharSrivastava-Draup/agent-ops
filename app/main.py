from fastapi import FastAPI

from app.api.jenkins_routes import router as jenkins_router
from app.api.routes import router as api_router
from app.config import get_settings
from app.utils.logging import configure_logging


def create_app() -> FastAPI:
    """Instantiate FastAPI application with configured routers."""
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    application.include_router(api_router, prefix="/api")
    application.include_router(jenkins_router, prefix="/api/jenkins", tags=["Jenkins"])
    return application


app = create_app()

