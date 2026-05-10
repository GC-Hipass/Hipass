#!/usr/bin/env bash
# 개발 환경 부트스트랩 + 서버 실행 (Mac / Linux / WSL).
#
# 사용법:
#   bash scripts/dev.sh              # 세팅 + uvicorn 실행
#   bash scripts/dev.sh --skip-run   # 세팅만
#   bash scripts/dev.sh --reinstall  # venv 재생성
#   PORT=8001 bash scripts/dev.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

VENV_DIR="$PROJECT_ROOT/.venv"
VENV_PY="$VENV_DIR/bin/python"
REQ_FILE="$PROJECT_ROOT/requirements.txt"
REQ_HASH_FILE="$VENV_DIR/.requirements.sha256"
PORT="${PORT:-8002}"

skip_run=0
reinstall=0
for arg in "$@"; do
    case "$arg" in
        --skip-run) skip_run=1 ;;
        --reinstall) reinstall=1 ;;
        *) echo "[dev] 알 수 없는 옵션: $arg"; exit 1 ;;
    esac
done

resolve_python() {
    for cand in python3.10 python3.11 python3.12 python3 python; do
        if command -v "$cand" >/dev/null 2>&1; then
            ver=$("$cand" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")') || continue
            major="${ver%%.*}"; minor="${ver##*.}"
            if [[ "$major" == "3" && "$minor" -ge 10 && "$minor" -lt 13 ]]; then
                echo "$cand"
                return 0
            fi
        fi
    done
    echo "[dev] Python 3.10~3.12 가 필요합니다." >&2
    return 1
}

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

# 1) venv
if [[ "$reinstall" == "1" && -d "$VENV_DIR" ]]; then
    echo "[dev] 기존 venv 제거..."
    rm -rf "$VENV_DIR"
fi

if [[ ! -x "$VENV_PY" ]]; then
    PY="$(resolve_python)"
    echo "[dev] venv 생성 ($PY)"
    "$PY" -m venv "$VENV_DIR"
    "$VENV_PY" -m pip install --upgrade pip --quiet
fi

# 2) 의존성
current_hash="$(sha256 "$REQ_FILE")"
installed_hash=""
[[ -f "$REQ_HASH_FILE" ]] && installed_hash="$(cat "$REQ_HASH_FILE")"

if [[ "$current_hash" != "$installed_hash" ]]; then
    echo "[dev] requirements.txt 변경 감지 — 의존성 동기화"
    "$VENV_PY" -m pip install -r "$REQ_FILE"
    echo "$current_hash" > "$REQ_HASH_FILE"
else
    echo "[dev] 의존성 최신 (skip)"
fi

# 3) .env
if [[ ! -f "$PROJECT_ROOT/.env" && -f "$PROJECT_ROOT/.env.example" ]]; then
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo
    echo "[dev] .env 가 없어 .env.example 을 복사했습니다."
    echo "      DATABASE_URL / NCLOUD / CLOVA 키를 채운 뒤 다시 실행하세요."
    echo
fi

# 4) 실행
if [[ "$skip_run" == "1" ]]; then
    echo "[dev] 세팅 완료 (실행 생략)"
    exit 0
fi

echo "[dev] uvicorn http://localhost:$PORT"
exec "$VENV_PY" -m uvicorn app.main:app --reload --port "$PORT"
