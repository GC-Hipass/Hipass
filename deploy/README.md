# Hipass Backend Deployment

Target app server:

```text
hp-dev-app-srv01
internal IP: 10.0.2.6
service: hipass-app
port: 8000
```

## Server Layout

```text
/root/Hipass
  app/
  requirements.txt
  .venv/
  .env
  _storage/
    audio/
    documents/
```

## Runtime Wiring

```text
Nginx web server: 101.79.17.102
  -> FastAPI app server: 10.0.2.6:8000
  -> DB server: 10.0.3.7:5432
  -> LLM server: 10.0.4.6:8000
```

## Required App Env

```env
APP_NAME=navercloud-ai-interview
APP_ENV=prod
LOG_LEVEL=INFO

DATABASE_URL=postgresql+psycopg://hpuser:<URL_ENCODED_DB_PASSWORD>@10.0.3.7:5432/hpdb

LLM_PROVIDER=external
LLM_SERVER_URL=http://10.0.4.6:8000
LLM_REQUEST_TIMEOUT_SECONDS=180

STT_PROVIDER=clova
EMBEDDING_PROVIDER=local
EMBEDDING_DIMENSION=384

LOCAL_STORAGE_DIR_VOICE=/root/Hipass/_storage/audio
LOCAL_STORAGE_DIR_DOCUMENT=/root/Hipass/_storage/documents
```

Use `STT_PROVIDER=mock` only for smoke tests. Use `STT_PROVIDER=clova` for real interview runs.

## Deploy Changed Backend Files

From local Windows PowerShell:

```powershell
cd C:\Users\ksyzi\PycharmProjects\ncloud\navercloud-ai

scp -o ProxyJump=root@101.79.17.102 `
  .\app\api\v1\endpoints\upload.py `
  .\app\api\v1\endpoints\questions.py `
  .\app\api\v1\endpoints\evaluate.py `
  .\app\api\v1\endpoints\result.py `
  root@10.0.2.6:/root/Hipass/app/api/v1/endpoints/

scp -o ProxyJump=root@101.79.17.102 `
  .\app\rag\providers\llm.py `
  root@10.0.2.6:/root/Hipass/app/rag/providers/

scp -o ProxyJump=root@101.79.17.102 `
  .\app\rag\pipelines\question_generation.py `
  .\app\rag\pipelines\answer_evaluation.py `
  root@10.0.2.6:/root/Hipass/app/rag/pipelines/

scp -o ProxyJump=root@101.79.17.102 `
  .\app\rag\prompts\question_prompts.py `
  root@10.0.2.6:/root/Hipass/app/rag/prompts/
```

Then on app server:

```bash
ssh -J root@101.79.17.102 root@10.0.2.6

cd /root/Hipass
/root/Hipass/.venv/bin/python -m compileall app
systemctl restart hipass-app
sleep 3
systemctl status hipass-app --no-pager
journalctl -u hipass-app -f
```

## Smoke Checks

App server:

```bash
curl http://127.0.0.1:8000/health
curl http://10.0.4.6:8000/health
```

Web server:

```bash
curl http://101.79.17.102/health
```

LLM generate from app server:

```bash
curl --connect-timeout 30 --max-time 240 \
  -X POST http://10.0.4.6:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"백엔드 연결 테스트야. 한 문장으로 답해줘.","temperature":0.1,"max_tokens":50}'
```

## Logs

```bash
journalctl -u hipass-app -f
journalctl -u hipass-app -n 100 --no-pager -l
```

Nginx logs on web server:

```bash
tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```

## Current Long Task Behavior

- Upload returns quickly and starts question generation in background.
- Question lookup waits for generated questions.
- Final answer submission starts evaluation in background.
- Result lookup waits for evaluation completion.

This is a backend-only compatibility layer for the current frontend.
