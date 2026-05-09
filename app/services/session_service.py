from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import SessionNotFound
from app.db.models import InterviewSession
from app.schemas.common import Company, Difficulty, JobRole


def create_session(
    db: Session, *, company: Company, difficulty: Difficulty, job_role: JobRole
) -> InterviewSession:
    s = get_settings()
    session = InterviewSession(
        company=company.value,
        difficulty=difficulty.value,
        job_role=job_role.value,
        status="created",
        question_count=s.question_count,
        recording_seconds=s.recording_seconds,
    )
    db.add(session)
    db.flush()
    return session


def get_session(db: Session, session_id: int) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if not session:
        raise SessionNotFound(f"세션 {session_id}을(를) 찾을 수 없습니다.")
    return session


def update_status(db: Session, session: InterviewSession, status: str) -> InterviewSession:
    session.status = status
    if status in {"completed", "evaluated"}:
        session.completed_at = datetime.now(timezone.utc)
    db.flush()
    return session
