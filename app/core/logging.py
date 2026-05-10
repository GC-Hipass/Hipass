import logging
import sys

from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    root = logging.getLogger()
    # uvicorn이 먼저 핸들러를 등록하더라도 레벨은 항상 덮어쓴다
    root.setLevel(level)

    # 핸들러가 없을 때만 추가 (중복 방지)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root.addHandler(handler)
    else:
        # uvicorn 핸들러에도 동일한 레벨 적용
        for h in root.handlers:
            h.setLevel(level)

    # uvicorn 내부 로거가 ERROR로 덮어쓰는 것을 방지
    for name in ("uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(level)
