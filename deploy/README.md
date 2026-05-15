# navercloud-ai app server deployment

Target server: `hp-dev-app-srv01` (`10.0.2.6`)

## Runtime wiring

```text
nginx/web -> app server:8002 -> db server:10.0.3.7:5432
                         -> llm server:10.0.4.6:8000
```

## Environment

Copy `deploy/app.env.example` to the deployed app root as `.env`, then fill secret values.

Important server values:

```env
APP_ENV=prod
DATABASE_URL=postgresql+psycopg://hpuser:<URL_ENCODED_DB_PASSWORD>@10.0.3.7:5432/hpdb
LLM_PROVIDER=external
LLM_SERVER_URL=http://10.0.4.6:8000
EMBEDDING_PROVIDER=local
EMBEDDING_DIMENSION=384
```

Use `STT_PROVIDER=mock` only for smoke tests. Use `STT_PROVIDER=clova` for real speech-to-text.
Embeddings are generated on the app server by the local SentenceTransformer model
`paraphrase-multilingual-MiniLM-L12-v2`; the Ncloud Embedding API env values are not used by the current code.

## Smoke checks

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
curl http://127.0.0.1:8002/health
curl http://10.0.4.6:8000/health
```
