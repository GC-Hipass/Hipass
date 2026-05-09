from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class InterviewAnswer(Base, TimestampMixin):
    __tablename__ = "interview_answers"
    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_answer_session_question"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    audio_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stt_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="clova_speech")
    recording_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
