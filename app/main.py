from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import setup_logging

# Configure logging before uvicorn attaches its own handlers.
setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.should_bootstrap_db:
        from app.db.base import Base
        from app.db.session import engine, ensure_pgvector_extension

        ensure_pgvector_extension()
        from app.db import models  # type: ignore  # noqa: F401

        Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    local_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    allowed_origins = settings.cors_origins or (local_origins if settings.app_env == "local" else [])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
