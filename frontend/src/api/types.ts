// 백엔드 DTO와 1:1 대응. CLAUDE.md 명세 기준.

export type Company = "naver" | "sk" | "samsung";
export type Difficulty = "easy" | "normal" | "hard";
export type JobRole = "app" | "web" | "ai" | "devops";

export interface UploadResponse {
  session_id: number;
  document_id: number;
  file_type: string;
  company: Company;
  difficulty: Difficulty;
  job_role: JobRole;
  question_count: number;
  recording_seconds: number;
  status: string;
}

export interface QuestionResponse {
  session_id: number;
  question_id: number;
  order: number;
  question: string;
  tts_audio_url: string;
  tts_duration_seconds: number | null;
  recording_seconds: number;
}

export interface QAItem {
  order: number;
  question_id: number;
  question: string;
  answer: string;
  score: number;
  feedback: string;
}

export interface Analysis {
  summary: string;
  strengths: string[];
  weaknesses: string[];
  recommendation: string;
}

export interface EvaluationPayload {
  evaluation_id: number;
  total_score: number;
  grade: string;
  qa_list: QAItem[];
  analysis: Analysis;
}

export interface AnswerResponse {
  answer_id: number;
  session_id: number;
  question_id: number;
  order: number;
  answer_text: string;
  stt_provider: string;
  answered_count: number;
  question_count: number;
  is_session_completed: boolean;
  is_evaluated: boolean;
  evaluation: EvaluationPayload | null;
}

export interface EvaluationResultResponse {
  session_id: number;
  evaluation_id: number;
  total_score: number;
  grade: string;
  qa_list: QAItem[];
  analysis: Analysis;
}

export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
}
