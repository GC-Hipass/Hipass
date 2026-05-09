from fastapi import APIRouter

from app.api.v1.endpoints import audio, evaluate, questions, result, upload

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(questions.router, tags=["questions"])
api_router.include_router(audio.router, tags=["audio"])
api_router.include_router(evaluate.router, tags=["evaluate"])
api_router.include_router(result.router, tags=["result"])
