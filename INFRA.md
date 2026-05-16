# Hi-Pass 인프라 아키텍처

## 1. 인프라 개요

"Hi-Pass" 서비스의 인프라는 네이버 클라우드 플랫폼(Ncloud) 위에 구축했습니다.
VPC(Virtual Private Cloud)를 기반으로 서브넷을 역할별로 분리하고, 외부에 노출되는 서버와 내부에서만 동작하는 서버를 명확히 구분하여 보안성과 확장성을 확보했습니다.

프론트엔드는 Vercel에 배포하여 글로벌 CDN으로 빠르게 서빙하고, 백엔드 API와 AI 파이프라인은 Ncloud VPC 내부에서 안전하게 처리합니다.

---

## 2. 사용 기술

| 구분 | 기술 |
| --- | --- |
| 클라우드 플랫폼 | Naver Cloud Platform (Ncloud) |
| 네트워크 | VPC, Subnet (Public/Private), NAT Gateway |
| 웹 서버 (Reverse Proxy) | Nginx |
| 앱 서버 | FastAPI (Python) + Uvicorn |
| 데이터베이스 | Ncloud Cloud DB for PostgreSQL + pgvector |
| AI 서버 | 자체 LLM 서버 (GPU) |
| 외부 AI 서비스 | Ncloud Clova Speech STT, Clova Voice TTS, Clova X (Fallback) |
| 프론트엔드 배포 | Vercel (CDN) |
| 보안 그룹 | ACG (Access Control Group) |
| 서버 접근 관리 | Bastion Host (SSH 우회 접속) |

---

## 3. 전체 아키텍처 흐름

### 요청 흐름 (번호는 아키텍처 다이어그램 기준)

```
① 사용자가 브라우저에서 Hi-Pass 서비스에 접속
② Vercel(CDN)이 프론트엔드 화면(React)을 사용자 브라우저에 전달
③ 사용자의 API 요청(문서 업로드, 질문 조회 등)이 Nginx 웹 서버로 전달
④ Nginx가 내부 FastAPI 앱 서버로 요청을 프록시(전달)
⑤ FastAPI가 RAG 파이프라인 실행 (문서 파싱 → 청킹 → 임베딩 → 검색)
⑥ 임베딩된 벡터를 PostgreSQL + pgvector에서 유사도 검색
⑦ 검색된 문맥을 기반으로 자체 LLM 서버에 질문 생성/답변 평가 요청
⑧ 필요 시 Ncloud Clova 서비스(STT/TTS/Clova X Fallback) 호출
```

### 응답 흐름

```
LLM/Clova 응답 → FastAPI가 결과 가공 → Nginx 경유 → 사용자 브라우저에 표시
```

---

## 4. 네트워크 설계

### VPC 및 서브넷 구성

하나의 VPC 안에 역할별로 서브넷을 분리하여, 각 서버가 최소한의 통신만 허용되도록 설계했습니다.

| 서브넷 | 유형 | 대역 | 배치된 서버 | 역할 |
| --- | --- | --- | --- | --- |
| hp-pub-web-sn | Public | 10.0.1.0/24 | 웹 서버 (Nginx) | 외부 트래픽을 받는 유일한 진입점 |
| hp-pub-app-sn | Public → Private 전환 예정 | 10.0.2.0/24 | 앱 서버 (FastAPI) | API 비즈니스 로직 및 RAG 처리 |
| hp-pvt-db-sn | Private | 10.0.3.0/24 | DB 서버 (PostgreSQL) | 데이터 저장 및 벡터 검색 |
| hp-pvt-llm-sn | Private | 10.0.4.0/24 | LLM 서버 (GPU) | AI 추론 처리 |

### Public vs Private 서브넷의 차이

- **Public 서브넷**: 서버에 공인 IP를 부여할 수 있어 외부 인터넷에서 직접 접근이 가능합니다. 웹 서버처럼 외부 사용자의 요청을 받아야 하는 서버에 사용합니다.
- **Private 서브넷**: 공인 IP가 없어 외부에서 절대 직접 접근할 수 없습니다. DB나 LLM처럼 내부에서만 사용되는 민감한 서버에 사용하여 보안을 강화합니다.

### 서브넷 분리의 이유

서버를 하나의 네트워크에 모두 몰아넣으면 관리는 편하지만, 한 대가 뚫리면 나머지 서버도 모두 위험해집니다. 서브넷을 분리하면 웹 서버가 해킹되더라도 DB 서버나 LLM 서버는 별도의 네트워크에 격리되어 있어 피해를 최소화할 수 있습니다.

---

## 5. 서버 구성

### 서버 인벤토리

| 서버명 | 용도 | 공인 IP | 사설 IP | 서브넷 |
| --- | --- | --- | --- | --- |
| hp-dev-web-srv01 | 웹 서버 (Nginx) | 101.79.17.102 | 10.0.1.6 | hp-pub-web-sn |
| hp-dev-app-srv01 | 앱 서버 (FastAPI) | 향후 제거 예정 | 10.0.2.6 | hp-pub-app-sn |
| hp-dev-llm-srv01 | LLM 서버 (GPU) | 없음 | 10.0.4.6 | hp-pvt-llm-sn |
| hp-dev-db-svr01 | DB 서버 (PostgreSQL) | 없음 | 10.0.3.7 | hp-pvt-db-sn |

### 각 서버의 역할

**웹 서버 (Nginx) — 리버스 프록시 + Bastion Host**

외부 인터넷과 내부 서버 사이의 중간 관문 역할을 합니다. Vercel에서 날아오는 API 요청을 받아 내부의 FastAPI 서버로 전달(프록시)합니다. HTTPS 암호화 종료(SSL Termination), 비정상 요청 차단, 로드 밸런싱 등의 보안 기능도 수행합니다.
또한 개발자가 내부 서버(App, LLM, DB)에 SSH로 접속할 때 반드시 이 웹 서버를 먼저 거쳐야 하는 Bastion Host(점프 서버) 역할도 겸합니다.

**앱 서버 (FastAPI) — 비즈니스 로직 + RAG 처리**

서비스의 모든 핵심 로직이 실행되는 서버입니다. 문서 업로드 처리, RAG 파이프라인(파싱 → 청킹 → 임베딩 → 검색), 질문 생성/답변 평가 요청, DB 읽기/쓰기, 외부 Clova API 호출 등을 담당합니다.
보안을 위해 향후 Private 서브넷으로 이전하여 외부에서 직접 접근할 수 없도록 할 예정입니다.

**LLM 서버 (GPU) — AI 추론**

GPU가 탑재된 서버로, 질문 생성과 답변 평가에 필요한 LLM 추론을 수행합니다. Private 서브넷에 배치되어 오직 앱 서버의 요청만 받습니다. 외부 인터넷에 직접 노출되지 않으므로 모델 파일과 GPU 자원을 안전하게 보호합니다.

**DB 서버 (PostgreSQL + pgvector) — 데이터 및 벡터 저장**

Ncloud의 관리형 DB(Cloud DB for PostgreSQL)를 사용합니다. 면접 세션, 질문, 답변, 평가 결과 등 정형 데이터와 pgvector 확장을 통한 임베딩 벡터 데이터를 모두 저장합니다. Private 서브넷에 배치되어 오직 앱 서버만 접근 가능합니다.

---

## 6. 보안 설계 (ACG)

### ACG (Access Control Group)란?

네이버 클라우드에서 제공하는 서버 단위 방화벽입니다. AWS의 Security Group과 동일한 개념으로, 각 서버에 "어떤 IP에서, 어떤 포트로 들어오는 트래픽만 허용할 것인지"를 규칙으로 정의합니다. 규칙에 없는 트래픽은 모두 차단(Deny)됩니다.

### 보안 설계 원칙

1. **최소 권한 원칙 (Least Privilege)**: 각 서버는 바로 앞단의 서버에서 오는 트래픽만 허용합니다. 불필요한 포트는 열지 않습니다.
2. **체인형 접근 제어**: 외부 → Web → App → DB/LLM 순서로만 트래픽이 흐르도록 설계했습니다. DB 서버가 웹 서버와 직접 통신하거나, 외부에서 DB에 직접 접근하는 것은 불가능합니다.
3. **서버별 전용 ACG**: 공통 ACG 대신 각 서버의 역할에 맞는 전용 ACG를 할당하여 규칙을 명확하게 관리합니다.

### ACG 규칙 상세

**웹 서버 ACG (hp-web-acg)**

외부 사용자(Vercel)의 HTTP/HTTPS 접근과 관리자의 SSH 접근을 허용합니다.

| 프로토콜 | 접근 소스 | 포트 | 용도 |
| --- | --- | --- | --- |
| TCP | 0.0.0.0/0 | 80 | HTTP 통신 (Vercel → Nginx) |
| TCP | 0.0.0.0/0 | 443 | HTTPS 통신 (Vercel → Nginx) |
| TCP | 관리자 IP 대역 | 22 | SSH 관리용 |

- 80/443 포트를 0.0.0.0/0으로 여는 것은 웹 서버의 본질적 역할(외부 요청 수신)에 해당하므로 정상적인 설정입니다.

**앱 서버 ACG (hp-app-acg)**

오직 웹 서버(Nginx)의 API 전달과 SSH 우회 접속만 허용합니다.

| 프로토콜 | 접근 소스 | 포트 | 용도 |
| --- | --- | --- | --- |
| TCP | 10.0.1.6/32 (웹 서버) | 8000 | FastAPI 통신 (Nginx → App) |
| TCP | 10.0.1.6/32 (웹 서버) | 22 | SSH 관리용 (Bastion 경유) |

- 접근 소스가 웹 서버의 사설 IP 한 대로만 제한되어 있어, 외부에서 앱 서버로 직접 접근하는 것은 불가능합니다.

**LLM 서버 ACG (hp-llm-acg)**

앱 서버의 추론 요청과 SSH 관리 접속만 허용합니다.

| 프로토콜 | 접근 소스 | 포트 | 용도 |
| --- | --- | --- | --- |
| TCP | 10.0.2.6/32 (앱 서버) | 8000 | LLM API 통신 (App → LLM) |
| TCP | 10.0.2.6/32 (앱 서버) | 22 | SSH 관리용 (App 서버 경유) |

- 코드 배포, 모델 파일 교체, 로그 확인 등의 관리 작업을 위해 SSH 접속이 필요합니다. 접근 소스를 앱 서버로 제한하여 외부 직접 접근은 차단합니다.

**DB 서버 ACG**

앱 서버의 데이터베이스 커넥션과 Ncloud 자체 관리용 포트를 허용합니다.

| 프로토콜 | 접근 소스 | 포트 | 용도 |
| --- | --- | --- | --- |
| TCP | 10.0.2.6/32 (앱 서버) | 5432 | PostgreSQL 통신 (App → DB) |
| TCP | cloud-postgresql (Ncloud) | 20021 | Ncloud 자체 관리용 (자동 생성) |
| TCP | cloud-postgresql (Ncloud) | 5432 | Ncloud 자체 관리용 (자동 생성) |

- Ncloud 관리형 DB(Cloud DB for PostgreSQL)는 OS 레벨 SSH 접속이 제공되지 않으므로 22번 포트는 불필요합니다. DB 관리가 필요한 경우 앱 서버에서 `psql` 명령어로 원격 접속하여 수행합니다.

### 트래픽 흐름 요약

```
외부 사용자(Vercel)
  ↓ HTTPS (443)
[웹 서버 - Nginx] 10.0.1.6
  ↓ HTTP (8000)
[앱 서버 - FastAPI] 10.0.2.6
  ├── TCP (5432) → [DB 서버 - PostgreSQL] 10.0.3.7
  ├── HTTP (8000) → [LLM 서버 - GPU] 10.0.4.6
  └── HTTPS → [Ncloud Clova STT/TTS/LLM] (외부 API)
```

---

## 7. NAT Gateway

### NAT Gateway란?

Private 서브넷에 배치된 서버는 공인 IP가 없어 외부 인터넷에 접속할 수 없습니다. 하지만 서버 운영을 위해 패키지 설치(pip install, apt-get)나 외부 API 호출이 필요한 경우가 있습니다. NAT Gateway는 이런 Private 서버들이 외부 인터넷으로 **나갈 수만 있도록** 일방통행 통로를 제공합니다. 외부에서 NAT Gateway를 통해 내부로 들어오는 것은 불가능합니다.

### NAT Gateway 구성

| 항목 | 값 |
| --- | --- |
| 이름 | hp-dev-nat-gw-01 |
| 공인 IP | 101.79.22.59 |
| 사설 IP | 10.0.5.6 |

### 라우팅 테이블 설정

Private 서브넷의 서버가 외부로 나가려 할 때(목적지 0.0.0.0/0), NAT Gateway를 경유하도록 라우팅을 설정했습니다.

| 라우트 테이블 | 적용 서브넷 | 목적지 | 타겟 |
| --- | --- | --- | --- |
| hipass-vpc-default-private-table | hp-pvt-db-sn (10.0.3.0/24) | 0.0.0.0/0 | hp-dev-nat-gw-01 |
| hipass-vpc-default-private-table | hp-pvt-llm-sn (10.0.4.0/24) | 0.0.0.0/0 | hp-dev-nat-gw-01 |

---

## 8. 프론트엔드 배포 (Vercel)

### Vercel을 선택한 이유

프론트엔드(React)를 별도의 서버 없이 Vercel에 배포하여 인프라 관리 부담을 줄이고, 글로벌 CDN을 통해 빠른 페이지 로딩을 제공합니다.

### 배포 방식

1. GitHub 레포지토리의 `frontend/` 디렉토리를 Vercel에 연결합니다.
2. 코드가 Push되면 Vercel이 자동으로 빌드 및 배포합니다 (CI/CD).
3. Vercel 환경 변수에 백엔드 API 주소(Nginx 서버의 공인 IP 또는 도메인)를 설정하여 프론트엔드와 백엔드를 연결합니다.

### 프론트엔드와 백엔드의 분리

프론트엔드와 백엔드는 동일한 GitHub 레포지토리(모노레포)에서 관리하지만, 배포는 완전히 분리됩니다.

| 구분 | 배포 위치 | 포트/주소 | 역할 |
| --- | --- | --- | --- |
| 프론트엔드 (React) | Vercel (CDN) | https://도메인.vercel.app | UI 렌더링 및 사용자 인터랙션 |
| 백엔드 (FastAPI) | Ncloud VPC 내부 | Nginx 공인 IP:443 → FastAPI:8000 | API 처리, RAG, DB 연동 |

---

## 9. 서버 접근 관리 (Bastion Host)

### Bastion Host란?

외부에서 내부 Private 서버에 접근해야 할 때, 직접 접속하는 대신 공인 IP를 가진 특정 서버를 중간 다리(점프 서버)로 사용하는 보안 기법입니다. 본 인프라에서는 웹 서버(hp-dev-web-srv01)가 Bastion Host 역할을 겸합니다.

### 접속 흐름

```
개발자 PC
  ↓ SSH (22번 포트)
[웹 서버] 101.79.17.102 (공인 IP)
  ↓ SSH (22번 포트, 사설 IP 통신)
[앱 서버] 10.0.2.6
  ↓ SSH (필요 시, 사설 IP 통신)
[LLM 서버] 10.0.4.6 또는 [DB 서버] 10.0.3.7
```

- 개발자가 앱 서버에 접속하려면 반드시 웹 서버를 먼저 경유해야 합니다.
- 외부에서 앱/LLM/DB 서버로의 직접 접속은 공인 IP가 없어 물리적으로 불가능합니다.

---

## 10. 인프라 설계 시 고민한 점

**보안과 개발 편의성의 균형**

Private 서브넷에 서버를 격리하면 보안은 강화되지만, 개발자가 서버에 접근하기 불편해집니다. 이를 해결하기 위해 웹 서버를 Bastion Host로 활용하여 보안을 유지하면서도 SSH 우회 접속이 가능하도록 했습니다.

**서브넷 분리 전략**

모든 서버를 한 서브넷에 넣으면 관리가 쉽지만, 한 서버가 뚫리면 전체가 위험해집니다. 역할별(Web, App, DB, AI)로 서브넷을 분리하고, 각 서브넷 간 통신을 ACG로 최소화하여 침해 시 피해 범위를 제한(Blast Radius 최소화)했습니다.

**NAT Gateway 도입**

Private 서브넷의 서버도 패키지 설치나 외부 API 호출이 필요합니다. NAT Gateway를 두어 "안에서 밖으로만" 나갈 수 있는 일방통행 통로를 만들어, 외부 접근 차단은 유지하면서 서버 운영에 필요한 아웃바운드 통신은 보장했습니다.

**프론트엔드와 백엔드의 물리적 분리**

프론트엔드를 Vercel(CDN)에, 백엔드를 Ncloud VPC에 각각 배포하여 역할을 분담했습니다. 프론트엔드는 CDN의 글로벌 캐싱으로 빠른 로딩을, 백엔드는 VPC의 네트워크 격리로 보안을 각각 극대화했습니다. 이를 통해 프론트엔드 트래픽이 백엔드 서버에 부하를 주지 않고, 백엔드 장애 시에도 프론트엔드 화면 자체는 정상 표시됩니다.
