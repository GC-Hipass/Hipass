# navercloud-ai

문서 기반 RAG 면접 평가 서비스 (FastAPI + Ncloud).

서비스/도메인 명세는 [`CLAUDE.md`](./CLAUDE.md), RAG 파이프라인 개요는 [`RAG.md`](./RAG.md) 참고.

---

## 디렉토리 구조

```
app/
├── api/                # FastAPI 라우팅 (HTTP I/O 전용)
│   └── v1/endpoints/   # upload, questions, audio, evaluate, result
├── core/               # 설정, 예외, 로깅, 에러 핸들러
├── db/                 # SQLAlchemy 세션 + ORM 모델
│   └── models/         # documents, chunks, sessions, questions, answers, evaluations, knowledge
├── schemas/            # Pydantic I/O 스키마
├── services/           # 도메인 비즈니스 로직 (API ↔ RAG 가교)
└── rag/                # RAG 모듈 (API와 독립)
    ├── parser/         # PDF/DOCX/TXT 텍스트 추출
    ├── chunker/        # 텍스트 분할
    ├── embedding (providers/embedding)  # Ncloud Embedding
    ├── vectorstore/    # pgvector
    ├── retrieval/      # Hybrid + Rerank
    ├── prompts/        # 질문 생성 / 답변 평가 프롬프트
    ├── providers/      # LLM·TTS·STT·ObjectStorage 추상화
    └── pipelines/      # LangGraph 질문 생성, 답변 평가
```

### 계층 규칙

- `api` → `services` 만 호출 (RAG 직접 호출 금지)
- `services` → `rag.pipelines` / `rag.indexing` / `rag.providers` / `db.models`
- `rag/*` 는 외부 모듈을 import하지 않음 (단, `db.models`만 사용 — pgvector 컬럼 정의 공유 목적)
- 외부 SaaS(Ncloud)는 모두 `rag/providers/` 의 추상 클래스 뒤에 숨김 → 구현체 교체 시 `factory`만 수정

---

## 빠른 시작

> 사전 조건: **Python 3.10 ~ 3.12** 설치 (`.python-version` 참고). PostgreSQL + pgvector 는 Ncloud 에 구축되어 있다고 가정.

### Windows (PowerShell)

```powershell
git clone <repo>
cd navercloud-ai
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```

### Mac / Linux / WSL

```bash
git clone <repo>
cd navercloud-ai
bash scripts/dev.sh
```

스크립트가 자동으로 처리하는 것:

1. Python 3.10~3.12 탐지
2. `.venv/` 생성 (없을 때만)
3. `requirements.txt` 동기화 (해시 변경 시에만 재설치)
4. `.env` 가 없으면 `.env.example` 복사 후 종료 → 키 채우고 다시 실행
5. `uvicorn app.main:app --reload --port 8000` 실행

### 옵션

| 옵션 | Windows | Unix |
| --- | --- | --- |
| 세팅만, 실행 X | `scripts\dev.ps1 -SkipRun` | `bash scripts/dev.sh --skip-run` |
| venv 재생성 | `scripts\dev.ps1 -Reinstall` | `bash scripts/dev.sh --reinstall` |
| 포트 변경 | `scripts\dev.ps1 -Port 8001` | `PORT=8001 bash scripts/dev.sh` |

### 수동 실행 (스크립트 없이)

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

### Swagger

http://localhost:8000/docs

### .env 필수 항목

`.env.example` 의 모든 항목 중 다음만 채우면 동작:

- `DATABASE_URL` — Ncloud Postgres + pgvector 접속 URL (`postgresql+psycopg://...`)
- `CLOVA_X_API_KEY`
- `CLOVA_VOICE_CLIENT_ID` / `CLOVA_VOICE_CLIENT_SECRET`
- `CLOVA_SPEECH_API_URL` / `CLOVA_SPEECH_SECRET`
- `NCLOUD_EMBEDDING_API_URL` / `NCLOUD_EMBEDDING_API_KEY`

`OBJECT_STORAGE_*` 는 비워두면 로컬 디스크(`_storage/`)에 저장 — 개발 시 편리.

### 마이그레이션

`APP_ENV=local` 일 때 부팅 시 `CREATE EXTENSION vector` 와 테이블이 자동 생성됩니다. 운영 배포 시에는 alembic 등 별도 마이그레이션을 권장.

---

## API 요약

| Method | Endpoint | 설명 |
| --- | --- | --- |
| `POST` | `/api/v1/upload` | 문서 + 옵션 업로드 → 질문 5개 생성 + TTS |
| `GET`  | `/api/v1/{session_id}/questions/{order}` | 순서별 질문 + TTS URL |
| `GET`  | `/api/v1/audio/questions/{question_id}` | 질문 TTS 오디오 (audio/mpeg) |
| `POST` | `/api/v1/{session_id}/evaluate` | 답변 오디오 업로드 + STT, 5번째면 RAG 평가 |
| `GET`  | `/api/v1/{session_id}/result` | 평가 결과 조회 |

---

## RAG 확장 가이드

### 질문 생성 파이프라인 변경
- `app/rag/pipelines/question_generation.py` 의 `_build_graph`에서 LangGraph 노드 추가/순서 변경
- 프롬프트만 바꿀 경우 `app/rag/prompts/question_prompts.py`

### 평가 파이프라인 변경
- `app/rag/pipelines/answer_evaluation.py` 의 `_evaluate_one` (개별 문항) / `_final_analysis` (총평)
- 점수 가중치는 `_SCORE_WEIGHTS` 상수

### Ncloud 외 다른 provider로 교체
- 각 provider는 ABC를 구현하므로 새 클래스 작성 후 `get_*_provider()` factory에서 분기
- API/services 코드는 변경 없음

### 사전 임베딩 적재
- `knowledge_documents` / `knowledge_chunks` 테이블에 `source_type ∈ {company_profile, technical_knowledge, personality_question}` 으로 직접 INSERT
- 별도 admin 스크립트는 추후 추가 (`app/rag/indexing.py` 의 `DocumentIndexer` 와 동일한 패턴 활용 가능)
