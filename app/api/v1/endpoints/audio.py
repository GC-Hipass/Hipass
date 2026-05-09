from fastapi import APIRouter, Path
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import DBSession
from app.services import question_service

router = APIRouter()


@router.get("/audio/questions/{question_id}")
def get_question_audio(
    question_id: int = Path(..., ge=1),
    db: Session = DBSession,
) -> Response:
    audio_bytes, content_type = question_service.get_question_audio(db, question_id)
    return Response(
        content=audio_bytes,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
