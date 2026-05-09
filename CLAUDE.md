# 문서 기반 RAG 면접 평가 서비스 개발 문서

## 1. 서비스 개요

이 서비스는 개인 포트폴리오, PDF/DOCX/TXT 문서를 업로드하면 선택한 기업과 직무에 맞춰 AI 모의면접 질문을 생성하고, 사용자의 음성 답변을 평가하는 백엔드 시스템이다.

질문은 Clova Voice를 사용해 음성으로 안내한다. 사용자는 질문 음성을 들은 뒤 30초 동안 답변하고, 녹음 파일은 서버로 전송된다. 백엔드는 Clova Speech로 STT를 수행한 뒤 답변을 저장하고, 5개 답변이 모두 완료되면 RAG 기반 평가를 실행한다.

전체 환경은 Ncloud 사용을 기준으로 한다.

## 2. 사용 기술

| 구분 | 기술 |
| --- | --- |
| Backend | FastAPI |
| 문서 파싱 | PDF, DOCX, TXT parser |
| TTS | Ncloud Clova Voice |
| STT | Ncloud Clova Speech |
| LLM | Naver CLOVA X |
| Embedding Model | Ncloud Embedding Model |
| Vector DB | Ncloud Vector DB 또는 PostgreSQL + pgvector |
| Orchestration | LangGraph |
| DB | PostgreSQL |

## 3. 핵심 요구사항

| 항목 | 내용 |
| --- | --- |
| 업로드 파일 | `.pdf`, `.docx`, `.txt` |
| 질문 개수 | 총 5개 |
| 녹음 시간 | 질문당 30초 |
| 질문 안내 | Clova Voice TTS |
| 답변 인식 | Clova Speech STT |
| 평가 방식 | RAG + CLOVA X |
| 결과 | 점수, 질문/답변 목록, 잘한 점, 부족한 점, 개선점 |

## 4. 사용자 흐름

```text
1. 사용자가 문서 업로드
2. 기업, 난이도, 직무 선택
3. 백엔드가 문서 파싱
4. 문서 chunk 분할
5. embedding 생성
6. Vector DB 저장
7. RAG 기반 질문 5개 생성
8. 질문별 Clova Voice TTS 생성
9. 생성된 TTS 오디오 파일의 재생 길이 계산
10. 프론트에서 질문 음성 재생
11. TTS 재생 완료 후 녹음 시작 (자동으로)
12. 사용자가 종료 버튼 클릭 또는 30초 타임아웃
13. 녹음 파일 서버 전송
14. 백엔드가 Clova Speech STT 수행
15. 답변 저장 (프론트에서 일단 저장하고 5번째때 다 보냄)
16. 5개 답변 완료 시 RAG 평가 실행
17. 점수와 분석 결과 반환
```

## 5. API 기본 정보

| 항목 | 값 |
| --- | --- |
| Base URL | `/api/v1` |
| 문서 업로드 형식 | `multipart/form-data` |
| 답변 업로드 형식 | `multipart/form-data` |
| 일반 요청 형식 | `application/json` |
| 업로드 가능 파일 | `.pdf`, `.docx`, `.txt` |

## 6. 공통 옵션

| 구분 | 값 |
| --- | --- |
| 기업 | `naver`, `sk`, `samsung` |
| 난이도 | `easy`, `normal`, `hard` |
| 직무 | `app`, `web`, `ai`, `devops` |

## 7. API 목록

| Method | Endpoint | 설명 |
| --- | --- | --- |
| `POST` | `/upload` | 문서 업로드 + 옵션 선택 -> 서버에서 질문 5개 생성 + 질문 TTS 생성 |
| `GET` | `/audio/questions/{question_id}` | 질문 TTS 오디오 파일 (key로 object storage로 요청) 조회 + 이후 답변 녹음 기능 활성화 |
| `POST` | `/{session_id}/evaluate` | 답변 오디오 업로드 + STT + 답변 저장 + 5번째면 RAG 평가 |
| `GET` | `/{session_id}/result` | 평가 결과 조회 |

## 8. 문서 업로드 API

```http
POST /api/v1/upload
```

PDF, DOCX, TXT 파일 중 하나를 업로드하고 기업, 난이도, 직무를 선택한다.

백엔드는 업로드된 문서에서 텍스트를 추출하고, chunk로 분할한 뒤 embedding을 생성해 저장한다. 이후 선택한 조건을 기준으로 질문 5개를 생성하고, 각 질문에 대해 Clova Voice로 TTS 음성을 생성한다.

### Request

Content-Type:

```text
multipart/form-data
```

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `file` | File | Y | 업로드할 문서 파일. `.pdf`, `.docx`, `.txt` 허용 |
| `company` | string | Y | `samsung`, `sk`, `naver` |
| `difficulty` | string | Y | `easy`, `normal`, `hard` |
| `job_role` | string | Y | `app`, `web`, `ai`, `devops` |

### Response `200 OK`

```json
{
  "session_id": 1,
  "document_id": 10,
  "file_type": "pdf",
  "company": "samsung",
  "difficulty": "normal",
  "job_role": "web",
  "question_count": 5,
  "recording_seconds": 30,
  "status": "question_generated"
}
```

### Backend 처리

```text
1. 파일 확장자 검증
2. 문서 메타데이터 저장
3. 파일 형식별 텍스트 추출
4. 텍스트 chunk 분할
5. chunk별 embedding 생성
6. Vector DB에 chunk + embedding 저장
7. company / difficulty / job_role 조건 기반 질문 5개 생성
8. 질문 저장
9. 질문별 Clova Voice TTS 생성
10. 생성된 TTS 오디오 파일의 재생 길이 계산
11. tts_audio_path, tts_duration_seconds 저장
12. session_id 반환
```
--------------------


## 9. 통합 질문 조회 & TTS 오디오 API

```http
GET /api/v1/{session_id}/questions/{order}
```

- 특정 세션(`session_id`)에서 **질문 순서(order)**에 맞는 질문과 TTS 오디오를 함께 반환합니다.  
- 프론트는 질문을 하나씩 요청하면서 표시 → TTS 재생 → 녹음 시작을 진행합니다.

---

### Response `200 OK`

```json
{
  "session_id": 1,
  "question_id": 101,
  "order": 1,
  "question": "웹 성능 최적화 방법에 대해 설명해 주세요.",
  "tts_audio_url": "/api/v1/audio/questions/101",
  "tts_duration_seconds": 4.8,
  "recording_seconds": 30
}
```

---

### 🔄 프론트엔드 처리 흐름

```text
1. /api/v1/{session_id}/questions/{order} 호출
2. 질문 텍스트 표시
3. tts_audio_url 재생
4. TTS 재생 완료 이벤트 감지 
5. 재생 완료(초로 감지) 즉시 녹음 시작
6. 재생 완료 이벤트 누락 시 tts_duration_seconds 이후 녹음 시작
7. 사용자가 종료 버튼 클릭 또는 recording_seconds(30초) 타임아웃
8. 녹음 파일을 evaluate API로 전송
```

-----------------------

## 11. 답변 오디오 저장 및 RAG 평가 API

```http
POST /api/v1/{session_id}/evaluate
```

프론트가 녹음한 답변 오디오 파일을 서버로 전송한다.

백엔드는 Clova Speech로 STT를 수행하고 답변 텍스트를 저장한다.

답변이 1~4번째라면 저장 결과만 반환한다.

답변이 5번째라면 자동으로 RAG 평가를 실행하고 최종 평가 결과까지 반환한다.

### Request

Content-Type:

```text
multipart/form-data
```

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `question_id` | integer | Y | 질문 ID |
| `audio` | File | Y | 사용자 답변 녹음 파일 |
| `recording_duration_seconds` | integer | Y | 실제 녹음 시간 |

### Response `200 OK` - 1~4번째 답변 저장 시

```json
{
  "answer_id": 1001,
  "session_id": 1,
  "question_id": 101,
  "order": 1,
  "answer_text": "이미지 최적화, 코드 스플리팅, 캐싱 등을 통해 웹 성능을 개선할 수 있습니다.",
  "stt_provider": "clova_speech",
  "answered_count": 1,
  "question_count": 5,
  "is_session_completed": false,
  "is_evaluated": false,
  "evaluation": null
}
```

### Response `200 OK` - 5번째 답변 저장 및 평가 완료 시

```json
{
  "answer_id": 1005,
  "session_id": 1,
  "question_id": 105,
  "order": 5,
  "answer_text": "장애 상황에서는 로그와 메트릭을 확인하고 원인을 좁혀가야 합니다.",
  "stt_provider": "clova_speech",
  "answered_count": 5,
  "question_count": 5,
  "is_session_completed": true,
  "is_evaluated": true,
  "evaluation": {
    "evaluation_id": 5001,
    "total_score": 78,
    "grade": "B",
    "qa_list": [
      {
        "order": 1,
        "question_id": 101,
        "question": "웹 성능 최적화 방법에 대해 설명해 주세요.",
        "answer": "이미지 최적화, 코드 스플리팅, 캐싱 등을 통해 웹 성능을 개선할 수 있습니다.",
        "score": 80,
        "feedback": "핵심 방향은 맞지만 구체적인 실무 예시가 부족합니다."
      }
    ],
    "analysis": {
      "summary": "전체적으로 기본 개념은 이해하고 있으나 답변이 짧고 구체성이 부족합니다.",
      "strengths": [
        "핵심 키워드를 언급함"
      ],
      "weaknesses": [
        "문서 근거 기반 설명이 부족함",
        "실무 적용 사례가 부족함"
      ],
      "recommendation": "정의, 이유, 예시 순서로 답변하는 연습이 필요합니다."
    }
  }
}
```

### Backend 처리

```text
1. session_id 유효성 확인
2. question_id가 해당 세션의 질문인지 확인
3. 중복 답변 여부 확인
4. 답변 오디오 파일 저장
5. Clova Speech STT 호출
6. STT 결과 answer_text 저장
7. 현재까지 저장된 답변 개수 확인

8. answered_count < 5인 경우
   - 저장 결과만 반환
   - is_session_completed = false
   - evaluation = null

9. answered_count == 5인 경우
   - session 상태를 completed로 변경
   - 질문/답변 5개 조회
   - 질문/답변 기반으로 관련 문서 chunk 검색
   - LLM 평가 실행
   - evaluation 결과 저장
   - session 상태를 evaluated로 변경
   - 평가 결과 포함해서 반환
```

## 12. 평가 결과 조회 API

```http
GET /api/v1/{session_id}/result
```

이미 생성된 평가 결과를 다시 조회한다.

### Response `200 OK`

```json
{
  "session_id": 1,
  "evaluation_id": 5001,
  "total_score": 78,
  "grade": "B",
  "qa_list": [
    {
      "order": 1,
      "question_id": 101,
      "question": "웹 성능 최적화 방법에 대해 설명해 주세요.",
      "answer": "이미지 최적화, 코드 스플리팅, 캐싱 등을 통해 웹 성능을 개선할 수 있습니다.",
      "score": 80,
      "feedback": "핵심 방향은 맞지만 구체적인 실무 예시가 부족합니다."
    }
  ],
  "analysis": {
    "summary": "전체적으로 기본 개념은 이해하고 있으나 답변이 짧고 구체성이 부족합니다.",
    "strengths": [
      "핵심 키워드를 언급함"
    ],
    "weaknesses": [
      "문서 근거 기반 설명이 부족함",
      "실무 적용 사례가 부족함"
    ],
    "recommendation": "정의, 이유, 예시 순서로 답변하는 연습이 필요합니다."
  }
}
```

## 13. 주요 에러

| Status | Code | 설명 |
| --- | --- | --- |
| `400` | `INVALID_FILE_TYPE` | `.pdf`, `.docx`, `.txt`가 아닌 파일 |
| `400` | `INVALID_OPTION` | 기업/난이도/직무 값 오류 |
| `400` | `ANSWER_ALREADY_EXISTS` | 이미 답변한 질문 |
| `400` | `INVALID_AUDIO_FILE` | 지원하지 않는 오디오 파일 |
| `400` | `SESSION_NOT_COMPLETED` | 5개 답변 전 결과 조회 |
| `404` | `SESSION_NOT_FOUND` | 세션 없음 |
| `404` | `QUESTION_NOT_FOUND` | 질문 없음 |
| `500` | `DOCUMENT_PARSE_FAILED` | 문서 텍스트 추출 실패 |
| `500` | `EMBEDDING_FAILED` | 임베딩 생성 실패 |
| `500` | `TTS_FAILED` | Clova Voice TTS 실패 |
| `500` | `STT_FAILED` | Clova Speech STT 실패 |
| `500` | `LLM_EVALUATION_FAILED` | LLM 평가 실패 |

## 14. RAG 전체 구조

RAG는 두 개의 파이프라인으로 구성한다.

```text
1. 질문 생성 RAG
2. 답변 평가 RAG
```

사전에 아래 문서들은 미리 임베딩해 둔다.

```text
1. 기업 인재상 문서
2. 개발 관련 문서
3. 인성 평가 질문 리스트
```

사용자가 업로드하는 문서는 세션 단위로 별도 임베딩한다.

## 15. 질문 생성 RAG

### 목적

업로드 문서, 기업, 난이도, 직무 조건을 기반으로 면접 질문 5개를 생성한다.

질문 구성:

| 질문 유형 | 개수 |
| --- | --- |
| 인성 질문 | 1 |
| 일반 개발 상식 질문 | 1 |
| 업로드 문서 기반 질문 | 2 |
| 기업 특화 질문 | 1 |

### 입력

| 입력 | 설명 |
| --- | --- |
| 업로드 문서 | 개인 포트폴리오, 잡코리아 이력서, 학습 문서 |
| company | `samsung`, `sk`, `naver` |
| difficulty | `easy`, `normal`, `hard` |
| job_role | `app`, `web`, `ai`, `devops` |

### 파이프라인

```text
Document Upload
   ↓
Text Extraction
   ↓
Chunking
   ↓
Embedding
   ↓
Vector DB 저장
   ↓
Metadata Filtering
   ↓
Hybrid Retrieval
   ↓
Reranking
   ↓
Prompt Augmentation
   ↓
CLOVA X Question Generation
   ↓
Clova Voice TTS 생성
   ↓
질문 5개 저장
```

### Retrieval 전략

| 기법 | 목적 |
| --- | --- |
| Metadata Filtering | 기업, 직무, 난이도 기준으로 검색 범위 제한 |
| Hybrid Search | semantic search + keyword search 결합 |
| Multi Query Retrieval | 같은 조건에서 여러 검색 쿼리 생성 |
| Reranking | 검색된 chunk의 관련도 재정렬 |

### LangGraph 사용 방식

LangGraph는 Retrieval 자체보다 질문 생성 orchestration 용도로 사용한다.

```text
START
  ↓
Load Session Options
  ↓
Retrieve Personality Context
  ↓
Retrieve Technical Context
  ↓
Retrieve Uploaded Document Context
  ↓
Retrieve Company Context
  ↓
Generate 5 Questions
  ↓
Validate Question Types
  ↓
Generate TTS
  ↓
END
```

### 질문 생성 Prompt 개념

```text
너는 IT 기업 면접관이다.

아래 조건에 맞춰 면접 질문 5개를 생성해라.

[기업]
{company}

[난이도]
{difficulty}

[직무]
{job_role}

[개인 문서 내용]
{uploaded_document_context}

[기업 인재상]
{company_context}

[개발 지식 문맥]
{technical_context}

[인성 평가 문맥]
{personality_context}

질문 구성:
1. 인성 질문 1개
2. 일반 개발 상식 질문 1개
3. 업로드 문서 기반 질문 2개
4. 기업 특화 질문 1개

반드시 JSON 배열로 반환해라.
```

## 16. 답변 평가 RAG

### 목적

사용자의 답변을 질문별로 평가하고, 점수와 피드백을 생성한다.

평가 기준:

```text
1. 질문 의도에 맞게 답했는가
2. 핵심 개념을 포함했는가
3. 문서 근거와 충돌하지 않는가
4. 논리적으로 설명했는가
5. 직무/기업 맥락에 맞는가
```

### 입력

| 입력 | 설명 |
| --- | --- |
| question | 면접 질문 |
| answer_text | Clova Speech로 변환된 사용자 답변 |
| uploaded_document_context | 업로드 문서 기반 검색 문맥 |
| company_context | 기업 인재상 검색 문맥 |
| technical_context | 개발 지식 검색 문맥 |

### 파이프라인

```text
Question
   ↓
User Audio Answer
   ↓
Clova Speech STT
   ↓
Answer Text 저장
   ↓
Context Retrieval
   ↓
Ideal Answer Generation
   ↓
User Answer Embedding
   ↓
Semantic Comparison
   ↓
Keyword Coverage Check
   ↓
LLM-based Evaluation
   ↓
Score + Feedback 반환
```

### 평가 방식

단순 cosine similarity만으로 평가하지 않는다.

모범답안 생성 기반 평가 방식을 사용한다.

```text
1. 질문 기준 관련 문맥 검색
2. 검색 문맥을 기반으로 모범답안 생성
3. 사용자 답변 embedding 생성
4. 모범답안과 사용자 답변 semantic similarity 비교
5. 핵심 키워드 포함 여부 분석
6. CLOVA X로 정성 평가 생성
7. 문항별 점수 산출
8. 전체 점수 합산
```

### 점수 산정 예시

| 항목 | 비중 |
| --- | --- |
| 의미 유사도 | 30 |
| 핵심 키워드 포함 | 25 |
| 문서 근거 일치 | 20 |
| 논리성 | 15 |
| 구체성 | 10 |

총점:

```text
question_score = semantic_score * 0.3
               + keyword_score * 0.25
               + groundedness_score * 0.2
               + logic_score * 0.15
               + specificity_score * 0.1

total_score = average(question_scores)
```

### 평가 결과 필드

각 질문마다 아래 내용을 생성한다.

```text
1. 사용자 답변
2. 잘 대답한 점
3. 잘못 대답한 점
4. 개선할 점
5. 점수
```

### 답변 평가 Prompt 개념

```text
너는 IT 기업 면접 답변 평가자다.

아래 문맥과 모범답안을 기준으로 사용자 답변을 평가해라.

[기업]
{company}

[직무]
{job_role}

[난이도]
{difficulty}

[질문]
{question}

[검색 문맥]
{retrieved_context}

[모범답안]
{ideal_answer}

[사용자 답변]
{user_answer}

평가 기준:
1. 질문 의도 일치
2. 핵심 개념 포함
3. 문서 근거 일치
4. 논리성
5. 구체성

아래 JSON 형식으로만 응답해라.
{
  "score": 0,
  "answer": "",
  "strengths": [],
  "weaknesses": [],
  "improvements": [],
  "feedback": ""
}
```

## 17. 권장 DB 테이블

### documents

```text
id
session_id
filename
file_type
file_hash
storage_path
created_at
```

### document_chunks

```text
id
document_id
session_id
chunk_index
content
embedding
metadata
created_at
```

### interview_sessions

```text
id
company
difficulty
job_role
status
question_count
recording_seconds
created_at
completed_at
```

### interview_questions

```text
id
session_id
order
question_type
question
tts_audio_path
tts_duration_seconds
created_at
```

### interview_answers

```text
id
session_id
question_id
order
audio_path
answer_text
stt_provider
recording_duration_seconds
created_at
```

### interview_evaluations

```text
id
session_id
total_score
grade
qa_result_json
analysis_json
created_at
```

### knowledge_documents

사전 임베딩 문서 저장용 테이블이다.

```text
id
source_type
company
job_role
difficulty
title
content
metadata
created_at
```

source_type 예시:

```text
company_profile
technical_knowledge
personality_question
```

### knowledge_chunks

```text
id
knowledge_document_id
source_type
company
job_role
difficulty
chunk_index
content
embedding
metadata
created_at
```

## 18. 구현 우선순위

| 순서 | 작업 |
| --- | --- |
| 1 | DB 테이블 설계 |
| 2 | 문서 업로드 API |
| 3 | PDF/DOCX/TXT 텍스트 추출 |
| 4 | chunking |
| 5 | Ncloud embedding 연동 |
| 6 | Vector DB 저장 |
| 7 | 질문 생성 RAG |
| 8 | Clova Voice TTS 생성 |
| 9 | 질문 조회 API |
| 10 | 답변 오디오 업로드 |
| 11 | Clova Speech STT |
| 12 | 답변 저장 |
| 13 | 답변 평가 RAG |
| 14 | 평가 결과 반환 |