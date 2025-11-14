from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.jenkins_routes import router as jenkins_router
from app.api.routes import router as api_router
from app.api.user_routes import router as user_router
from app.config import get_settings
from app.utils.logging import configure_logging


def create_app() -> FastAPI:
    """Instantiate FastAPI application with configured routers."""
    settings = get_settings()
    configure_logging(
        level=settings.log_level,
        log_file=settings.log_file,
        log_max_bytes=settings.log_max_bytes,
        log_backup_count=settings.log_backup_count,
    )
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Configure CORS
    # Allow all origins for development/testing (can be restricted in production)
    cors_origins = settings.cors_origins
    if cors_origins == ["*"] or "*" in cors_origins:
        # Allow all origins (cannot use credentials with wildcard)
        application.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Allow specific origins (can use credentials)
        application.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            allow_headers=["*"],
        )
    
    application.include_router(api_router, prefix="/api")
    application.include_router(jenkins_router, prefix="/api/jenkins", tags=["Jenkins"])
    application.include_router(user_router, prefix="/api/users", tags=["Users"])
    return application


app = create_app()

