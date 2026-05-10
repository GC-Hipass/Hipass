import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { ApiClientError } from "../api/client";
import { interviewApi } from "../api/interview";
import type { QuestionResponse } from "../api/types";
import { useRecorder } from "../hooks/useRecorder";
import VoiceWave from "../components/VoiceWave";
import styles from "./InterviewPage.module.css";

type Phase = "loading" | "playing-tts" | "recording" | "uploading" | "error";

const FALLBACK_QUESTION_COUNT = 5;
const FALLBACK_RECORDING_SECONDS = 30;

export default function InterviewPage() {
  const { sessionId, order } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const sessionIdNum = Number(sessionId);
  const orderNum = Number(order);

  const navState = location.state as
    | { questionCount?: number; recordingSeconds?: number }
    | null;
  const questionCount = navState?.questionCount ?? FALLBACK_QUESTION_COUNT;
  const recordingSeconds = navState?.recordingSeconds ?? FALLBACK_RECORDING_SECONDS;

  const [phase, setPhase] = useState<Phase>("loading");
  const [question, setQuestion] = useState<QuestionResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [remaining, setRemaining] = useState(recordingSeconds);

  const recorder = useRecorder();
  // recorder 객체는 매 렌더마다 새로 생성되지만, 내부 함수 레퍼런스는 안정적
  const recorderStart = recorder.start;
  const recorderStop = recorder.stop;
  const recorderRelease = recorder.release;

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<number | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // 타이머 콜백에서 stale closure 방지용 ref
  const finishAndUploadRef = useRef<() => Promise<void>>(async () => {});

  const finishAndUpload = useCallback(async () => {
    clearTimer();
    if (!question) return;
    setPhase("uploading");
    try {
      const clip = await recorderStop();
      if (!clip) {
        setErrorMessage("녹음된 데이터가 없습니다.");
        setPhase("error");
        return;
      }
      const res = await interviewApi.submitAnswer({
        sessionId: sessionIdNum,
        questionId: question.question_id,
        audio: clip.blob,
        audioFilename: clip.filename,
        durationSeconds: clip.durationSeconds,
      });

      if (res.is_session_completed && res.is_evaluated) {
        navigate(`/result/${sessionIdNum}`, { replace: true });
      } else {
        const next = orderNum + 1;
        if (next > questionCount) {
          navigate(`/result/${sessionIdNum}`, { replace: true });
        } else {
          navigate(`/interview/${sessionIdNum}/${next}`, {
            state: { questionCount, recordingSeconds },
            replace: true,
          });
        }
      }
    } catch (e) {
      const message =
        e instanceof ApiClientError ? `${e.code}: ${e.message}` : (e as Error).message;
      setErrorMessage(message);
      setPhase("error");
    }
  }, [
    clearTimer,
    navigate,
    orderNum,
    question,
    questionCount,
    recorderStop,
    recordingSeconds,
    sessionIdNum,
  ]);

  // 항상 최신 finishAndUpload를 ref에 유지
  useEffect(() => {
    finishAndUploadRef.current = finishAndUpload;
  }, [finishAndUpload]);

  const startRecording = useCallback(async () => {
    setPhase("recording");
    setRemaining(recordingSeconds);
    await recorderStart();

    timerRef.current = window.setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearTimer();
          void finishAndUploadRef.current();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, [recorderStart, recordingSeconds, clearTimer]);

  // 질문 로드 + TTS 재생 트리거
  useEffect(() => {
    let cancelled = false;
    setPhase("loading");
    setErrorMessage(null);
    setRemaining(recordingSeconds);

    interviewApi
      .getQuestion(sessionIdNum, orderNum)
      .then((q) => {
        if (cancelled) return;
        setQuestion(q);
        setPhase("playing-tts");
      })
      .catch((e) => {
        if (cancelled) return;
        const msg =
          e instanceof ApiClientError ? `${e.code}: ${e.message}` : (e as Error).message;
        setErrorMessage(msg);
        setPhase("error");
      });

    return () => {
      cancelled = true;
      clearTimer();
      recorderRelease();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionIdNum, orderNum]);

  // TTS 재생: phase=playing-tts 일 때 audio 엘리먼트 src 설정 + 자동 재생, 종료 시 녹음 시작
  useEffect(() => {
    if (phase !== "playing-tts" || !question) return;
    const audio = audioRef.current;
    if (!audio) return;

    audio.src = interviewApi.questionAudioUrl(question);

    const onEnded = () => {
      void startRecording();
    };
    audio.addEventListener("ended", onEnded);

    // duration 정보가 있으면 안전 타임아웃을 함께 걸어 재생 실패 시에도 진행되도록 함
    const fallbackMs = Math.max(2000, Math.round((question.tts_duration_seconds ?? 6) * 1000) + 2000);
    const fallbackTimer = window.setTimeout(() => {
      audio.removeEventListener("ended", onEnded);
      void startRecording();
    }, fallbackMs);

    audio.play().catch(() => {
      // 자동재생 차단 시 fallback 타임아웃이 처리
    });

    return () => {
      audio.removeEventListener("ended", onEnded);
      window.clearTimeout(fallbackTimer);
      audio.pause();
    };
  }, [phase, question, startRecording]);

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <div className={styles.badge}>
          Q{orderNum} / {questionCount}
        </div>
        <div className={styles.timerWrap}>
          <span className={styles.timerIcon} aria-hidden>
            ⏱
          </span>
          <span className={styles.timerText}>
            {phase === "recording" ? formatTime(remaining) : formatTime(recordingSeconds)}
          </span>
        </div>
      </header>

      <section className={styles.questionBox}>
        {phase === "loading" && <span className={styles.loadingText}>질문을 불러오는 중...</span>}
        {phase !== "loading" && question && (
          <p className={styles.questionText}>{question.question}</p>
        )}
      </section>

      <section className={styles.stage}>
        <div className={styles.avatarWrap}>
          <div className={`${styles.avatar} ${phase === "playing-tts" ? styles.avatarSpeaking : ""}`}>
            <div className={styles.avatarFace} aria-hidden>
              <span className={styles.avatarEye} />
              <span className={styles.avatarEye} />
            </div>
          </div>
          <div className={styles.avatarLabel}>면접관</div>
          {phase === "playing-tts" && <div className={styles.speakingBadge}>말하는 중</div>}
        </div>
      </section>

      <footer className={styles.bottomPanel}>
        <VoiceWave
          active={phase === "recording"}
          level={phase === "recording" ? recorder.audioLevel : 0}
        />

        <div className={styles.actions}>
          <span className={styles.statusHint}>
            {phase === "playing-tts" && "질문을 듣고 있어요"}
            {phase === "recording" && "답변을 녹음하고 있어요"}
            {phase === "uploading" && "답변을 전송하고 있어요"}
            {phase === "error" && (errorMessage ?? "오류가 발생했어요")}
            {phase === "loading" && "준비 중"}
          </span>

          <button
            className={styles.completeBtn}
            type="button"
            disabled={phase !== "recording"}
            onClick={() => void finishAndUpload()}
          >
            완료
          </button>
        </div>
      </footer>

      {/* hidden audio element for TTS playback */}
      <audio ref={audioRef} className={styles.hiddenAudio} preload="auto" />
    </div>
  );
}

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
