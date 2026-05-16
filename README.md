```md
# Hipass AI Interview Backend

문서 기반 RAG 면접 질문 생성 및 답변 평가 서비스입니다.

FastAPI 백엔드는 문서 업로드, 질문 생성, TTS/STT, 답변 저장, 평가 결과 조회를 담당합니다.  
LLM 추론은 백엔드 서버에서 직접 실행하지 않고, 별도 `ncloud-llm` 서버를 HTTP로 호출합니다.

## 아키텍처

```text
Frontend (Vercel)
  -> Nginx 웹 서버: 101.79.17.102
  -> FastAPI 앱 서버: 10.0.2.6:8000
  -> LLM API 서버: 10.0.4.6:8000
  -> Ollama: 127.0.0.1:11434

FastAPI 앱 서버
  -> PostgreSQL + pgvector: 10.0.3.7:5432
```

## 주요 기술 구성

| 영역 | 현재 구현 |
| --- | --- |
| Backend | FastAPI |
| DB | PostgreSQL + pgvector |
| LLM | 외부 `ncloud-llm` 서버 |
| LLM Runtime | Ollama |
| 현재 모델 | `qwen2.5:1.5b` |
| Embedding | 로컬 SentenceTransformer |
| Embedding 모델 | `paraphrase-multilingual-MiniLM-L12-v2` |
| TTS | Ncloud Clova Voice |
| STT | Ncloud Clova Speech |
| 문서 저장 | 기본 로컬 파일 시스템, Object Storage 선택 가능 |

## 주요 환경 변수

```env
APP_ENV=prod
DATABASE_URL=postgresql+psycopg://hpuser:<URL_ENCODED_PASSWORD>@10.0.3.7:5432/hpdb

LLM_PROVIDER=external
LLM_SERVER_URL=http://10.0.4.6:8000
LLM_REQUEST_TIMEOUT_SECONDS=180

EMBEDDING_PROVIDER=local
EMBEDDING_DIMENSION=384

STT_PROVIDER=clova
```
## 로컬 개발 실행

```powershell
cd C:\Users\ksyzi\PycharmProjects\ncloud\navercloud-ai

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8002
```

Swagger:

```text
http://127.0.0.1:8002/docs
```

프론트엔드 로컬 개발 환경은 일반적으로 백엔드 `8002` 포트로 프록시합니다.

## 운영 서버 서비스

앱 서버:

```bash
systemctl status hipass-app --no-pager
journalctl -u hipass-app -f
systemctl restart hipass-app
```

LLM 서버:

```bash
systemctl status ncloud-llm --no-pager
systemctl status ollama --no-pager
journalctl -u ncloud-llm -f
journalctl -u ollama -f
```

## API 요약

Base path:

```text
/api/v1
```

| Method | Endpoint | 설명 |
| --- | --- | --- |
| `POST` | `/upload` | 세션을 생성하고 문서 인덱싱/질문 생성을 백그라운드에서 시작 |
| `GET` | `/{session_id}/questions/{order}` | 생성된 질문과 TTS URL을 반환, 질문 생성 중이면 대기 |
| `GET` | `/audio/questions/{question_id}` | 생성된 질문 TTS 오디오 반환 |
| `POST` | `/{session_id}/evaluate` | 답변 오디오 저장, STT 실행, 마지막 답변이면 최종 평가를 백그라운드에서 시작 |
| `GET` | `/{session_id}/result` | 최종 평가 결과 반환, 평가 중이면 대기 |
| `GET` | `/debug/bucket` | 현재 저장소 설정 상태 확인 |

## 오래 걸리는 작업 처리 방식

현재 프론트엔드는 별도의 상태 polling API를 사용하도록 변경되어 있지 않습니다.  
따라서 백엔드에서 긴 작업을 흡수하는 방식으로 처리합니다.

1. `POST /upload`는 세션 생성 후 빠르게 응답하며, 응답 상태는 `question_processing`입니다.
2. 문서 처리, 질문 생성, TTS 생성은 FastAPI background task에서 처리됩니다.
3. `GET /{session_id}/questions/{order}`는 질문이 아직 생성 중이면 최대 180초까지 대기합니다.
4. `POST /{session_id}/evaluate`는 답변 저장과 STT 처리 후 응답합니다.
5. 마지막 답변이 제출되면 최종 평가는 background task에서 실행됩니다.
6. `GET /{session_id}/result`는 평가 결과가 아직 없으면 최대 300초까지 대기합니다.

이 구조는 프론트엔드를 다시 배포하지 않고 기존 흐름을 유지하기 위한 백엔드 호환 처리입니다.  
장기적으로는 프론트엔드에서 명시적인 상태 polling 구조를 사용하는 것이 권장됩니다.

## LLM API 명세

백엔드는 `LLM_SERVER_URL`에 설정된 LLM 서버를 호출합니다.

Health check:

```http
GET /health
```

Generate:

```http
POST /generate
Content-Type: application/json
```

Request:

```json
{
  "prompt": "prompt text",
  "system": "optional system prompt",
  "temperature": 0.2,
  "max_tokens": 1024
}
```

Response:

```json
{
  "text": "model output",
  "model": "qwen2.5:1.5b",
  "backend": "ollama"
}
```

## 참고 사항

- `.env` 파일에는 실제 키와 비밀번호가 포함되므로 절대 커밋하지 않습니다.
- `.env.example`, deploy 예시 env 파일에는 실제 secret 없이 필요한 키 목록만 문서화합니다.
- 현재 LLM 서버는 디스크 용량이 제한적입니다.
- `qwen2.5:7b`, `llama3.1:8b` 같은 더 큰 모델을 설치하려면 최소 30GB, 권장 50GB 이상의 디스크가 필요합니다.
```
