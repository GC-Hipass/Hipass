환경 : 전부 Ncloud 사용 (임베딩 벡터 db도 임베딩 모델도 네이버클라우드에 있는 모델 사용)
질문 생성 RAG / 답변 평가 RAG 두개의 파이프라인

  0.  기업인재상 문서, 개발 관련 문서, 인성평가 list는 사전에 임베딩됨

1. AI질문 생성 RAG ( 우리가 공부할거 알고 있는 pdf,docx,txt 및 옵션 선택(어떤 기업(삼성, sk, 네이버), 난이도(쉬움,중간 어려움), 직무 (웹, 앱, AI, 인프라 )를 업로드-> chunk-> 임베딩 -> 질문을 생성할때 Retrieval을 활용해서 문서 검색 (이때 langgraph는 LangGraph는 Retrieval 자체보다 “질문 orchestration” 용도로 사용+ ) -> 생성 (naver clova x를 사용 )-> 인성 질문 1개 일반적인 개발 상식 1개 내가 올린 문서에서 2개 기업 관련 문제 1개에 대한 질문을 반환
    - 파이프라인 구조
    
    ```
    PDF Upload
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
    Prompt Augmentation
       ↓
    CLOVA X Question Generation
    ```
    
    Retrieval 전략
    
    | 기법 | 목적 |
    | --- | --- |
    | Hybrid Search | semantic + keyword 검색 |
    | Metadata Filtering | 기업/직무 기반 filtering |
    | Multi Query Retrieval | 다양한 질문 생성 |
    | Reranking | 검색 정확도 향상 |
    
    생성 질문 구성
    
    | 질문 유형 | 개수 |
    | --- | --- |
    | 인성 질문 | 1 |
    | 개발 상식 | 1 |
    | 업로드 문서 기반 | 2 |
    | 기업 특화 질문 | 1 |
    
    LangGraph는 Retrieval 자체보다 “질문 orchestration” 용도로 사용.
    
    ```
    START
     ├── Personality Question
     ├── Technical Question
     ├── Company Question
     └── PDF-based Question
    END
    ```
    
    ---
    
2. 답변 평가 RAG ( 답변을 text로 받음 → chunking → 임베딩→ retrieval (각 질문에 대한 답변을 제대로 말했는지 각각 평가 (질문에 맞는 답변을 가상으로 생성하고 사용자의 답변과 유사도 평가하여 점수산출 → 5개를 각각 평가하고 점수 합산 → 어떤 방식으로 평가할것인지 RAG 기법을 제안)  → LLM(naverclova)로 각각 1.답변 2.잘 대답한점 3.잘못 대답한점 4.개선할 점으로 평가 텍스트 생성 → 점수와 분석 결과 반환
- Answer Evaluation RAG
    
    사용자의 답변을 기술 정확성,논리성,핵심 개념 포함 여부 기준으로 평가하고 피드백 생성.
    
- 평가 파이프라인

```
Question
   ↓
Context Retrieval
   ↓
Ideal Answer Generation
   ↓
User Answer Embedding
   ↓
Semantic Comparison
   ↓
LLM-based Evaluation
   ↓
Score + Feedback 반환
```

평가 방식

단순 cosine similarity 기반 평가 대신:

“모범답안 생성 기반 평가 방식” 적용.

평가 흐름

1. 질문 기반 모범답안 생성
2. 사용자 답변 임베딩
3. Semantic Similarity 비교
4. 핵심 키워드 포함 여부 분석
5. CLOVA X 기반 정성 평가