from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db


def db_session() -> Iterator[Session]:
    yield from get_db()


DBSession = Depends(db_session)
