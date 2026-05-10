import { audioUrl, getJson, postForm } from "./client";
import type {
  AnswerResponse,
  Company,
  Difficulty,
  EvaluationResultResponse,
  JobRole,
  QuestionResponse,
  UploadResponse,
} from "./types";

export interface UploadParams {
  file: File | null;
  company: Company;
  difficulty: Difficulty;
  jobRole: JobRole;
}

export const interviewApi = {
  upload(params: UploadParams): Promise<UploadResponse> {
    const form = new FormData();
    if (params.file) form.append("file", params.file);
    form.append("company", params.company);
    form.append("difficulty", params.difficulty);
    form.append("job_role", params.jobRole);
    return postForm<UploadResponse>("/api/v1/upload", form);
  },

  getQuestion(sessionId: number, order: number): Promise<QuestionResponse> {
    return getJson<QuestionResponse>(`/api/v1/${sessionId}/questions/${order}`);
  },

  questionAudioUrl(question: QuestionResponse): string {
    return audioUrl(question.tts_audio_url);
  },

  submitAnswer(params: {
    sessionId: number;
    questionId: number;
    audio: Blob;
    audioFilename: string;
    durationSeconds: number;
  }): Promise<AnswerResponse> {
    const form = new FormData();
    form.append("question_id", String(params.questionId));
    form.append("audio", params.audio, params.audioFilename);
    form.append("recording_duration_seconds", String(params.durationSeconds));
    return postForm<AnswerResponse>(`/api/v1/${params.sessionId}/evaluate`, form);
  },

  getResult(sessionId: number): Promise<EvaluationResultResponse> {
    return getJson<EvaluationResultResponse>(`/api/v1/${sessionId}/result`);
  },
};
