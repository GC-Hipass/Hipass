# RAG Pipeline Notes

이 문서는 현재 백엔드의 질문 생성 RAG와 답변 평가 RAG 흐름을 설명합니다.

## Overview

```text
Document upload
  -> text extraction
  -> chunking
  -> local embedding
  -> pgvector storage
  -> retrieval
  -> external LLM server
  -> question generation / answer evaluation
```

Current providers:

| Provider | Implementation |
| --- | --- |
| LLM | External `ncloud-llm` server |
| Embedding | Local SentenceTransformer |
| TTS | Ncloud Clova Voice |
| STT | Ncloud Clova Speech |
| Vector store | PostgreSQL + pgvector |

## Question Generation RAG

Purpose:

```text
Generate five interview questions from uploaded document content and selected options:
- company
- difficulty
- job role
```

Question composition:

| Type | Count |
| --- | --- |
| Personality | 1 |
| Technical/general development | 1 |
| Uploaded document based | 2 |
| Company specific | 1 |

Flow:

```text
1. User uploads PDF/DOCX/TXT.
2. Backend extracts text.
3. Text is split into chunks.
4. Chunks are embedded with local SentenceTransformer.
5. Chunks and vectors are stored in pgvector.
6. Retriever selects relevant uploaded-document and knowledge contexts.
7. Prompt is sent to the external LLM server.
8. LLM must return a JSON array of five questions.
9. Backend validates count and question shape.
10. Clova Voice creates TTS audio for each question.
11. Questions and TTS metadata are saved.
```

Important implementation files:

```text
app/rag/indexing.py
app/rag/pipelines/question_generation.py
app/rag/prompts/question_prompts.py
app/rag/providers/embedding.py
app/rag/providers/llm.py
app/rag/retrieval/
app/rag/vectorstore/
```

Current stability measures:

```text
- Lower question-generation temperature.
- Prompt requires JSON only.
- Prompt warns not to include literal line breaks inside JSON string values.
- LLM JSON parsing tries to extract fenced/raw JSON and repair control characters.
```

## Answer Evaluation RAG

Purpose:

```text
Evaluate all saved interview answers and create:
- question-level score
- question-level feedback
- overall score
- grade
- strengths
- weaknesses
- recommendation
```

Previous evaluation shape:

```text
For five questions:
- ideal answer generation per question
- per-question LLM scoring
- final analysis LLM call

Total: about 11 LLM calls
```

Current evaluation shape:

```text
For five questions:
- retrieve compact context per question
- send all questions and answers to the LLM in one batch
- parse one JSON response

Total: about 1 LLM call
```

This reduces latency and keeps the current frontend usable without a polling UI change.

Flow:

```text
1. User answers each question with audio.
2. Backend stores audio.
3. Clova Speech converts audio to answer text.
4. Backend stores answer text.
5. After the final answer, backend starts evaluation in a background task.
6. Evaluation pipeline retrieves compact contexts for each question.
7. A single batch prompt is sent to the external LLM server.
8. Backend parses JSON evaluation output.
9. Evaluation result is saved to interview_evaluations.
10. Session status changes to evaluated.
```

Important implementation files:

```text
app/api/v1/endpoints/evaluate.py
app/api/v1/endpoints/result.py
app/services/evaluation_service.py
app/rag/pipelines/answer_evaluation.py
app/rag/providers/llm.py
```

Fallback behavior:

```text
If batch LLM evaluation fails or returns invalid JSON, the backend creates fallback evaluation data.
This avoids turning every LLM formatting problem into a 500 response.
```

## Long-running Request Strategy

The current frontend is not changed. To avoid frontend timeout on long POST requests:

```text
POST /api/v1/upload
  -> returns quickly
  -> question generation runs in background

GET /api/v1/{session_id}/questions/{order}
  -> waits up to 180 seconds for generated questions

POST /api/v1/{session_id}/evaluate
  -> stores answer and returns
  -> final evaluation runs in background after last answer

GET /api/v1/{session_id}/result
  -> waits up to 300 seconds for evaluation result
```

Long-term recommended API design:

```text
POST /upload
GET /sessions/{session_id}/status
GET /questions/{order}
POST /answers
GET /result
```

The current implementation keeps compatibility with the existing frontend.

## LLM JSON Contract

Question generation expects a JSON array:

```json
[
  {
    "order": 1,
    "question_type": "personality",
    "question": "..."
  }
]
```

Answer evaluation expects a JSON object:

```json
{
  "qa_results": [
    {
      "order": 1,
      "question_id": 1,
      "score": 80,
      "feedback": "...",
      "strengths": ["..."],
      "weaknesses": ["..."],
      "improvements": ["..."]
    }
  ],
  "analysis": {
    "summary": "...",
    "strengths": ["..."],
    "weaknesses": ["..."],
    "recommendation": "..."
  }
}
```

## Notes

- Embedding dimension must match the DB vector column dimension. Current local model uses 384 dimensions.
- Do not switch between 1024-dimensional and 384-dimensional embedding providers without migrating/truncating vector data.
- Bigger LLM models should improve JSON reliability, but the LLM server needs more disk first.
