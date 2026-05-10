from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import setup_logging

# uvicorn보다 먼저 로깅 설정 — lifespan에서 호출하면 uvicorn 핸들러가 먼저 등록됨
setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.app_env == "local":
        # 로컬 개발 편의: pgvector 확장과 테이블을 자동 생성한다.
        # 운영에서는 alembic 마이그레이션 사용.
        from app.db.base import Base
        from app.db.session import engine, ensure_pgvector_extension

        ensure_pgvector_extension()
        # noqa — 모든 모델이 등록되도록 import
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=local_origins if settings.app_env == "local" else [],
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
