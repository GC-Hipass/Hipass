# navercloud-ai-frontend

React + TypeScript + Vite. AI 모의면접 웹 UI.

## 화면 구성

| 라우트 | 컴포넌트 | 역할 |
| --- | --- | --- |
| `/` | `SetupPage` | PDF 업로드 + 옵션(기업/난이도/직무) + 마이크·카메라 체크 |
| `/interview/:sessionId/:order` | `InterviewPage` | 질문 TTS 재생 → 30초 녹음 → 자동 다음 질문 |
| `/result/:sessionId` | `ResultPage` | 총점, 강점/약점, 개선 팁, 문항별 결과 |

## 백엔드 연동

`.env` 의 `VITE_API_BASE_URL` 이 백엔드 주소. 로컬 백엔드는 `http://localhost:8002`.

호출 매핑은 [src/api/interview.ts](src/api/interview.ts):

| 화면 동작 | 호출 |
| --- | --- |
| 문서 업로드 + 면접 시작 | `POST /api/v1/upload` |
| 질문 N번 조회 | `GET /api/v1/{session_id}/questions/{order}` |
| 질문 TTS mp3 재생 | `GET /api/v1/audio/questions/{question_id}` |
| 답변 녹음 업로드 | `POST /api/v1/{session_id}/evaluate` |
| 결과 재조회 | `GET /api/v1/{session_id}/result` |

## 빠른 시작

```powershell
cd frontend
copy .env.example .env
npm install
npm run dev      # http://localhost:5173
```

(Mac/Linux 는 `cp .env.example .env`)

## 디렉토리

```
src/
├── api/
│   ├── client.ts        # fetch 래퍼 + 에러 처리
│   ├── interview.ts     # 도메인 메서드
│   └── types.ts         # 백엔드 DTO 타입
├── components/
│   ├── VoiceWave.tsx    # 음성 입력 레벨 시각화 (24개 막대)
│   ├── ScoreCircle.tsx  # SVG 원형 점수
│   └── FeedbackList.tsx # 문항별 결과 카드
├── hooks/
│   ├── useRecorder.ts   # MediaRecorder + AnalyserNode (실시간 레벨)
│   └── useDeviceCheck.ts# 카메라/마이크 권한 + preview
├── pages/
│   ├── SetupPage.tsx
│   ├── InterviewPage.tsx
│   └── ResultPage.tsx
├── styles/
│   ├── tokens.css       # 색/간격/타이포 토큰
│   └── global.css
├── App.tsx              # 라우팅
└── main.tsx
```

## 색 시스템

[tokens.css](src/styles/tokens.css) — 일렉트릭 블루 베이스 + 다크 네이비 (Result Hero).

| 토큰 | 사용처 |
| --- | --- |
| `--brand-500` (#131EFF) | Primary CTA, 활성 옵션, 강조 텍스트 |
| `--brand-50/100` | 배지 배경, hover 보조 |
| `--surface-alt/soft` | 페이지·카드 배경 |
| `--result-bg-from/to` | 결과 페이지 hero 그라디언트 |
| `--warning` (#F59E0B) | 부족한 점 카드 강조 |

## 녹음/재생 흐름

`InterviewPage` 진입 시:

1. `GET /questions/{order}` 로 질문 + TTS URL + 재생 길이 확보
2. 숨겨진 `<audio>` 가 TTS 재생, `ended` 또는 `tts_duration_seconds + 2s` 안전 타임아웃 후 자동 녹음 시작
3. `useRecorder` 가 `audio/webm;codecs=opus` 또는 `audio/mp4`로 녹음, `AnalyserNode` 로 실시간 음성 레벨 추출 → `VoiceWave` 막대 높이에 반영
4. 30초 카운트다운 종료 또는 "완료" 클릭 → `POST /evaluate` 멀티파트 업로드
5. 1~4번째 답변이면 다음 order로 라우트 교체. 5번째이면 `/result/:sessionId` 로 이동

자동재생 차단(브라우저 정책)을 만나면 fallback 타임아웃이 처리하므로 흐름이 멈추지 않음.

## 음성 인식 형식

백엔드 [answer_service.py](../app/services/answer_service.py) 의 `_ALLOWED_EXTS` 와 `SUPPORTED_AUDIO_MIME` 에 맞춤:

- Chrome/Edge/Firefox: `audio/webm;codecs=opus` → `answer.webm`
- Safari: `audio/mp4` → `answer.mp4`

## 권한

마이크와 카메라 권한이 모두 거부되면 SetupPage 의 "면접 시작" 버튼이 비활성화됩니다 (마이크 미허용 시).
