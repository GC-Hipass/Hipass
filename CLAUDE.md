# Backend Development Notes

## Project Role

This repository contains the FastAPI backend for the Hipass AI interview service.

The backend owns:

```text
- document upload
- document parsing and chunking
- local embedding
- pgvector indexing
- question generation orchestration
- Clova Voice TTS
- Clova Speech STT
- answer storage
- answer evaluation orchestration
- result API
```

The backend does not run the main LLM model directly. It calls the separate `ncloud-llm` service.

## Runtime Topology

```text
Frontend
  -> Nginx web server
  -> FastAPI app server
  -> ncloud-llm server
  -> Ollama

FastAPI app server
  -> PostgreSQL + pgvector
```

Production app server:

```text
10.0.2.6:8000
```

Production LLM server:

```text
10.0.4.6:8000
```

## Key Environment Values

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

## Provider Boundaries

Use provider factories instead of calling external systems directly from endpoints.

```text
app/rag/providers/llm.py
app/rag/providers/embedding.py
app/rag/providers/tts.py
app/rag/providers/stt.py
app/rag/providers/object_storage.py
```

Current LLM provider:

```text
ExternalLLMProvider -> POST {LLM_SERVER_URL}/generate
```

Current embedding provider:

```text
Local SentenceTransformer: paraphrase-multilingual-MiniLM-L12-v2
```

## API Layer Rule

Endpoints should call services. Avoid putting RAG pipeline details directly in endpoints except for background task orchestration.

```text
api -> services -> rag pipelines/providers/vectorstore
```

## Current Long Task Compatibility Design

The frontend currently expects the old URL flow. To avoid requiring a frontend redeploy:

```text
POST /api/v1/upload
  -> creates session
  -> starts background question generation
  -> returns quickly

GET /api/v1/{session_id}/questions/{order}
  -> waits while questions are being generated

POST /api/v1/{session_id}/evaluate
  -> stores answer and STT text
  -> starts background final evaluation after last answer
  -> returns quickly

GET /api/v1/{session_id}/result
  -> waits while evaluation is running
```

This is a backend-only compatibility layer.

Long-term preferred design:

```text
POST /upload -> returns session_id
GET /status -> frontend polls
GET /questions/{order}
POST /answers
GET /result
```

## Session Status Values

Known statuses used by the current flow:

```text
created
question_processing
question_generated
question_generation_failed
evaluating
completed
evaluated
evaluation_failed
```

## Evaluation Pipeline

The answer evaluation pipeline now uses one batch LLM call for all answers.

Before:

```text
5 ideal-answer calls + 5 evaluation calls + 1 final analysis call
```

Now:

```text
1 batch evaluation call
```

This is faster and more stable for small CPU-only LLM servers.

## JSON Parsing

LLM output is not always strict JSON. `parse_json_loose` should:

```text
- strip markdown fences
- extract the first JSON object or array
- repair unescaped control characters inside JSON strings
```

Do not assume LLM output is clean.

## Local Commands

```powershell
cd C:\Users\ksyzi\PycharmProjects\ncloud\navercloud-ai

.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8002
```

## Production Commands

App server:

```bash
systemctl restart hipass-app
systemctl status hipass-app --no-pager
journalctl -u hipass-app -f
```

LLM server:

```bash
systemctl restart ncloud-llm
systemctl status ncloud-llm --no-pager
journalctl -u ncloud-llm -f
```

Ollama:

```bash
systemctl status ollama --no-pager
journalctl -u ollama -f
ollama list
```

## Git Notes

Do not commit real `.env` files or secrets.

Commit backend-only changes by staging explicit backend paths:

```powershell
git add `
  app/api/v1/endpoints/upload.py `
  app/api/v1/endpoints/questions.py `
  app/api/v1/endpoints/evaluate.py `
  app/api/v1/endpoints/result.py `
  app/rag/providers/llm.py `
  app/rag/pipelines/question_generation.py `
  app/rag/pipelines/answer_evaluation.py `
  app/rag/prompts/question_prompts.py `
  README.md RAG.md CLAUDE.md deploy/README.md
```
