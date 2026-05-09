from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import DBSession
from app.schemas.common import Company, Difficulty, JobRole
from app.schemas.upload import UploadResponse
from app.services import document_service, question_service, session_service

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    company: Company = Form(...),
    difficulty: Difficulty = Form(...),
    job_role: JobRole = Form(...),
    db: Session = DBSession,
) -> UploadResponse:
    raw = await file.read()

    session = session_service.create_session(
        db, company=company, difficulty=difficulty, job_role=job_role
    )

    document = document_service.store_and_index(
        db, session_id=session.id, filename=file.filename or "document", raw_bytes=raw
    )

    question_service.generate_questions_and_tts(db, session=session)
    session_service.update_status(db, session, "question_generated")
    db.commit()

    return UploadResponse(
        session_id=session.id,
        document_id=document.id,
        file_type=document.file_type,
        company=Company(session.company),
        difficulty=Difficulty(session.difficulty),
        job_role=JobRole(session.job_role),
        question_count=session.question_count,
        recording_seconds=session.recording_seconds,
        status=session.status,
    )
