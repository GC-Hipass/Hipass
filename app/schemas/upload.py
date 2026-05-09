from pydantic import BaseModel

from app.schemas.common import Company, Difficulty, JobRole


class UploadResponse(BaseModel):
    session_id: int
    document_id: int
    file_type: str
    company: Company
    difficulty: Difficulty
    job_role: JobRole
    question_count: int
    recording_seconds: int
    status: str
