import type { EvaluationResultResponse, QuestionResponse } from "../api/types";

export const DEMO_SESSION_ID = 999;
export const DEMO_QUESTION_COUNT = 5;
export const DEMO_RECORDING_SECONDS = 30;
export const DEMO_SEARCH = "?demo=1";

const DEMO_QUESTIONS = [
  "자기소개와 함께 최근에 가장 몰입해서 진행한 프로젝트를 간단히 설명해주세요.",
  "협업 중 의견 충돌이 생겼을 때 어떤 방식으로 정리하고 결론을 이끌어내시나요?",
  "프론트엔드 성능 문제를 직접 해결했던 경험이 있다면 원인과 개선 방법을 설명해주세요.",
  "사용자 경험을 높이기 위해 화면 흐름이나 인터랙션을 개선했던 사례가 있나요?",
  "우리 팀에 합류한다면 첫 한 달 동안 어떤 방식으로 적응하고 기여하실 건가요?",
];

export function isDemoMode(search: string): boolean {
  return new URLSearchParams(search).get("demo") === "1";
}

export function buildDemoQuestion(sessionId: number, order: number): QuestionResponse {
  const index = Math.min(Math.max(order - 1, 0), DEMO_QUESTIONS.length - 1);

  return {
    session_id: sessionId,
    question_id: 9000 + order,
    order,
    question: DEMO_QUESTIONS[index],
    tts_audio_url: "",
    tts_duration_seconds: null,
    recording_seconds: DEMO_RECORDING_SECONDS,
  };
}

export function buildDemoResult(sessionId: number): EvaluationResultResponse {
  return {
    session_id: sessionId,
    evaluation_id: 7001,
    total_score: 84,
    grade: "A",
    qa_list: DEMO_QUESTIONS.map((question, index) => ({
      order: index + 1,
      question_id: 9001 + index,
      question,
      answer: "데모 모드에서 생성된 예시 답변입니다.",
      score: [82, 86, 88, 81, 84][index],
      feedback: [
        "도입이 자연스럽고 핵심 경험을 빠르게 전달했습니다.",
        "갈등 해결 구조가 분명해 협업 역량이 잘 드러났습니다.",
        "문제 원인과 해결 과정을 구체적으로 설명해 설득력이 높았습니다.",
        "사용자 관점의 개선 포인트를 잘 짚었습니다.",
        "초기 적응 계획이 실무 중심으로 정리되어 인상이 좋습니다.",
      ][index],
    })),
    analysis: {
      summary: "전반적으로 구조화된 답변이 강점이며, 실무 경험 연결도 자연스러운 편입니다.",
      strengths: [
        "질문의 의도를 빠르게 파악하고 핵심을 먼저 말합니다.",
        "협업과 문제 해결 경험을 실무 언어로 정리하는 능력이 좋습니다.",
      ],
      weaknesses: [
        "일부 답변은 수치나 결과 지표가 더 들어가면 더 강해질 수 있습니다.",
        "임팩트 있는 결론 문장을 조금 더 짧게 정리할 여지가 있습니다.",
      ],
      recommendation: "답변 끝부분에 결과 수치와 배운 점을 한 문장씩 덧붙이면 완성도가 더 높아집니다.",
    },
  };
}
