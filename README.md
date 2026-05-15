# Hipass AI Interview Backend

문서 기반 RAG 면접 질문 생성 및 답변 평가 서비스입니다.

FastAPI 백엔드는 문서 업로드, 질문 생성, TTS/STT, 답변 저장, 평가 결과 조회를 담당하고,
LLM 추론은 별도 `ncloud-llm` 서버를 HTTP로 호출합니다.

## Architecture

```text
Frontend (Vercel)
  -> Nginx web server: 101.79.17.102
  -> FastAPI app server: 10.0.2.6:8000
  -> LLM API server: 10.0.4.6:8000
  -> Ollama: 127.0.0.1:11434

FastAPI app server
  -> PostgreSQL + pgvector: 10.0.3.7:5432
```

## Main Runtime Choices

| Area | Current implementation |
| --- | --- |
| Backend | FastAPI |
| DB | PostgreSQL + pgvector |
| LLM | External `ncloud-llm` server |
| LLM runtime | Ollama |
| Current model | `qwen2.5:1.5b` |
| Embedding | Local SentenceTransformer |
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` |
| TTS | Ncloud Clova Voice |
| STT | Ncloud Clova Speech |
| Document storage | Local filesystem by default, Object Storage optional |

## Important Environment

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

`NCLOUD_EMBEDDING_API_URL` and `NCLOUD_EMBEDDING_API_KEY` may exist in env files for compatibility,
but the current backend uses the local SentenceTransformer embedding provider.

## Local Development

```powershell
cd C:\Users\ksyzi\PycharmProjects\ncloud\navercloud-ai

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8002
```

Swagger:

```text
http://127.0.0.1:8002/docs
```

Frontend local dev normally proxies to backend port `8002`.

## Production Services

App server:

```bash
systemctl status hipass-app --no-pager
journalctl -u hipass-app -f
systemctl restart hipass-app
```

LLM server:

```bash
systemctl status ncloud-llm --no-pager
systemctl status ollama --no-pager
journalctl -u ncloud-llm -f
journalctl -u ollama -f
```

## API Summary

Base path:

```text
/api/v1
```

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/upload` | Create session and start document indexing/question generation in background |
| `GET` | `/{session_id}/questions/{order}` | Wait for and return a generated question with TTS URL |
| `GET` | `/audio/questions/{question_id}` | Return generated question TTS audio |
| `POST` | `/{session_id}/evaluate` | Store audio answer, run STT, and start final evaluation in background when complete |
| `GET` | `/{session_id}/result` | Wait for and return final evaluation result |
| `GET` | `/debug/bucket` | Check configured storage mode |

## Long-running Workflow Handling

The frontend is currently not changed to use explicit polling APIs, so the backend absorbs long work:

1. `POST /upload` returns quickly with `status=question_processing`.
2. Question generation and TTS run in a FastAPI background task.
3. `GET /{session_id}/questions/{order}` waits up to 180 seconds for questions.
4. `POST /{session_id}/evaluate` returns after answer storage/STT.
5. If the last answer was submitted, evaluation starts in a background task.
6. `GET /{session_id}/result` waits up to 300 seconds for the evaluation result.

This keeps the existing frontend flow working without a frontend redeploy.
The long-term recommended design is explicit status polling from the frontend.

## LLM API Contract

The backend calls the LLM server at `LLM_SERVER_URL`.

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

## Notes

- `.env` files contain secrets and must not be committed.
- `.env.example` and deploy example env files document required keys without real secrets.
- The current LLM server has limited disk. Use at least 30 GB, preferably 50 GB, before installing `qwen2.5:7b` or `llama3.1:8b`.
