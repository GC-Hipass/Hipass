from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import DBSession
from app.rag.providers.object_storage import NcloudObjectStorage, get_document_storage, get_voice_storage
from app.schemas.common import Company, Difficulty, JobRole
from app.schemas.upload import UploadResponse
from app.services import document_service, question_service, session_service

router = APIRouter()


@router.get("/debug/bucket", response_model=Dict[str, Any], tags=["debug"])
def debug_bucket() -> Dict[str, Any]:
    """음성/문서 버킷 접근 가능 여부를 각각 진단한다."""
    from app.core.config import get_settings
    s = get_settings()

    result: Dict[str, Any] = {
        "endpoint": s.object_storage_endpoint or "(비어있음)",
        "voice": {
            "bucket": s.object_storage_bucket_voice or "(비어있음)",
            "access_key_set": bool(s.object_storage_access_key_voice),
            "use_ncloud": s.use_voice_storage,
        },
        "document": {
            "bucket": s.object_storage_bucket_document or "(비어있음)",
            "access_key_set": bool(s.object_storage_access_key_document),
            "use_ncloud": s.use_document_storage,
        },
    }

    voice = get_voice_storage()
    result["voice"]["status"] = voice.debug_bucket() if isinstance(voice, NcloudObjectStorage) else "local"

    doc = get_document_storage()
    result["document"]["status"] = doc.debug_bucket() if isinstance(doc, NcloudObjectStorage) else "local"

    return result


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    company: Company = Form(...),
    difficulty: Difficulty = Form(...),
    job_role: JobRole = Form(...),
    db: Session = DBSession,
    file: Optional[UploadFile] = File(None),
) -> UploadResponse:
    session = session_service.create_session(
        db, company=company, difficulty=difficulty, job_role=job_role
    )

    document = None
    if file and file.filename:
        raw = await file.read()
        if raw:
            document = document_service.store_and_index(
                db, session_id=session.id, filename=file.filename, raw_bytes=raw
            )

    question_service.generate_questions_and_tts(db, session=session)
    session_service.update_status(db, session, "question_generated")
    db.commit()

    return UploadResponse(
        session_id=session.id,
        document_id=document.id if document else None,
        file_type=document.file_type if document else None,
        company=Company(session.company),
        difficulty=Difficulty(session.difficulty),
        job_role=JobRole(session.job_role),
        question_count=session.question_count,
        recording_seconds=session.recording_seconds,
        status=session.status,
    )
