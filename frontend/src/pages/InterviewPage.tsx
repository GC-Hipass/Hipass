import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { ApiClientError } from "../api/client";
import { interviewApi } from "../api/interview";
import type { QuestionResponse } from "../api/types";
import VoiceWave from "../components/VoiceWave";
import { useRecorder } from "../hooks/useRecorder";
import { buildDemoQuestion, DEMO_SEARCH, isDemoMode } from "../mocks/interviewDemo";
import styles from "./InterviewPage.module.css";

type Phase = "loading" | "playing-tts" | "recording" | "uploading" | "error";

const FALLBACK_QUESTION_COUNT = 5;
const FALLBACK_RECORDING_SECONDS = 30;

export default function InterviewPage() {
  const { sessionId, order } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const demoMode = isDemoMode(location.search);

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

  const finishAndUploadRef = useRef<() => Promise<void>>(async () => {});

  const finishAndUpload = useCallback(async () => {
    clearTimer();
    if (!question) return;

    if (demoMode) {
      const next = orderNum + 1;
      if (next > questionCount) {
        navigate({ pathname: `/result/${sessionIdNum}`, search: DEMO_SEARCH }, { replace: true });
      } else {
        navigate(
          { pathname: `/interview/${sessionIdNum}/${next}`, search: DEMO_SEARCH },
          {
            state: { questionCount, recordingSeconds },
            replace: true,
          },
        );
      }
      return;
    }

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
    demoMode,
    navigate,
    orderNum,
    question,
    questionCount,
    recorderStop,
    recordingSeconds,
    sessionIdNum,
  ]);

  useEffect(() => {
    finishAndUploadRef.current = finishAndUpload;
  }, [finishAndUpload]);

  const startRecording = useCallback(async () => {
    clearTimer();
    setErrorMessage(null);
    setRemaining(recordingSeconds);

    try {
      await recorderStart();
      setPhase("recording");
    } catch (e) {
      setErrorMessage((e as Error).message ?? "마이크 접근에 실패했습니다.");
      setPhase("error");
      return;
    }

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
  }, [clearTimer, recorderStart, recordingSeconds]);

  useEffect(() => {
    let cancelled = false;
    setPhase("loading");
    setErrorMessage(null);
    setRemaining(recordingSeconds);

    if (demoMode) {
      setQuestion(buildDemoQuestion(sessionIdNum, orderNum));
      setPhase("recording");
      return () => {
        clearTimer();
        recorderRelease();
      };
    }

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
  }, [demoMode, sessionIdNum, orderNum]);

  useEffect(() => {
    if (demoMode) return;
    if (phase !== "playing-tts" || !question) return;
    const audio = audioRef.current;
    if (!audio) return;

    audio.src = interviewApi.questionAudioUrl(question);

    const onEnded = () => {
      void startRecording();
    };
    audio.addEventListener("ended", onEnded);

    const fallbackMs = Math.max(
      2000,
      Math.round((question.tts_duration_seconds ?? 6) * 1000) + 2000,
    );
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
  }, [demoMode, phase, question, startRecording]);

  const phaseCopy = getPhaseCopy(phase, demoMode, errorMessage);
  const progressPercent = Math.min(100, Math.round((orderNum / Math.max(questionCount, 1)) * 100));
  const microphoneState =
    phase === "recording"
      ? `${Math.max(1, Math.round(recorder.audioLevel * 100))}% 입력 감지`
      : phase === "error"
        ? "재확인 필요"
        : "대기 중";

  return (
    <div className={styles.page}>
      <div className={styles.backdrop} aria-hidden />

      <header className={styles.topBar}>
        <div className={styles.sessionMeta}>
          <div className={styles.badge}>{demoMode ? "DEMO SESSION" : "LIVE SESSION"}</div>
          <div className={styles.progressText}>
            질문 {orderNum} / {questionCount}
          </div>
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

      <main className={styles.main}>
        <section className={styles.questionBox}>
          <div className={styles.questionMeta}>
            <span className={styles.phasePill}>{phaseCopy.label}</span>
            <div className={styles.progressBar}>
              <span className={styles.progressFill} style={{ width: `${progressPercent}%` }} />
            </div>
          </div>

          <span className={styles.questionLead}>Question {orderNum}</span>
          {phase === "loading" && <span className={styles.loadingText}>질문을 불러오는 중...</span>}
          {phase !== "loading" && question && (
            <p className={styles.questionText}>{question.question}</p>
          )}
          <p className={styles.questionSub}>{phaseCopy.description}</p>
        </section>

        <section className={styles.stage}>
          <div className={styles.stageGrid}>
            <div className={styles.avatarWrap}>
              <div className={styles.avatarShell}>
                <div className={styles.avatarAura} aria-hidden />
                <div className={`${styles.avatar} ${phase === "playing-tts" ? styles.avatarSpeaking : ""}`}>
                  <div className={styles.avatarFace} aria-hidden>
                    <span className={styles.avatarEye} />
                    <span className={styles.avatarEye} />
                  </div>
                </div>
              </div>
              <div className={styles.avatarLabel}>AI 면접관</div>
              {phase === "playing-tts" && <div className={styles.speakingBadge}>질문 전달 중</div>}
            </div>

            <div className={styles.sidePanel}>
              <article className={styles.infoCard}>
                <span className={styles.infoEyebrow}>FLOW</span>
                <h2 className={styles.infoTitle}>진행 단계</h2>
                <div className={styles.flowList}>
                  <div
                    className={`${styles.flowItem} ${
                      phase === "playing-tts" ? styles.flowItemActive : ""
                    } ${phase === "recording" || phase === "uploading" ? styles.flowItemDone : ""}`}
                  >
                    질문 듣기
                  </div>
                  <div
                    className={`${styles.flowItem} ${
                      phase === "recording" ? styles.flowItemActive : ""
                    } ${phase === "uploading" ? styles.flowItemDone : ""}`}
                  >
                    답변 녹음
                  </div>
                  <div
                    className={`${styles.flowItem} ${
                      phase === "uploading" ? styles.flowItemActive : ""
                    }`}
                  >
                    결과 전송
                  </div>
                </div>
              </article>

              <article className={styles.infoCard}>
                <span className={styles.infoEyebrow}>SESSION</span>
                <h2 className={styles.infoTitle}>현재 상태</h2>
                <div className={styles.statGrid}>
                  <div className={styles.statCard}>
                    <span className={styles.statLabel}>남은 시간</span>
                    <strong className={styles.statValue}>
                      {phase === "recording" ? formatTime(remaining) : formatTime(recordingSeconds)}
                    </strong>
                  </div>
                  <div className={styles.statCard}>
                    <span className={styles.statLabel}>마이크 입력</span>
                    <strong className={styles.statValue}>{microphoneState}</strong>
                  </div>
                </div>

                {demoMode && (
                  <div className={styles.demoNote}>
                    데모 모드에서는 녹음 업로드 없이 다음 질문으로 바로 이동합니다.
                  </div>
                )}

                {phase === "error" && (
                  <div className={styles.errorCard}>
                    {errorMessage ?? recorder.error ?? "오류가 발생했어요."}
                  </div>
                )}
              </article>
            </div>
          </div>
        </section>
      </main>

      <footer className={styles.bottomPanel}>
        <VoiceWave
          active={phase === "recording"}
          level={phase === "recording" ? recorder.audioLevel : 0}
        />

        <div className={styles.actions}>
          <span className={styles.statusHint}>{phaseCopy.description}</span>

          <div className={styles.actionButtons}>
            <button className={styles.secondaryBtn} type="button" onClick={() => navigate("/")}>
              종료
            </button>
            <button
              className={styles.completeBtn}
              type="button"
              disabled={phase !== "recording"}
              onClick={() => void finishAndUpload()}
            >
              {phase === "uploading" ? "전송 중..." : "답변 완료"}
            </button>
          </div>
        </div>
      </footer>

      <audio ref={audioRef} className={styles.hiddenAudio} preload="auto" />
    </div>
  );
}

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function getPhaseCopy(phase: Phase, demoMode: boolean, errorMessage: string | null): {
  label: string;
  description: string;
} {
  if (phase === "loading") {
    return {
      label: "Question Loading",
      description: "면접 질문과 세션 상태를 불러오고 있습니다.",
    };
  }

  if (phase === "playing-tts") {
    return {
      label: "Listen First",
      description: "질문을 끝까지 듣고 답변 흐름을 머릿속에서 정리해보세요.",
    };
  }

  if (phase === "recording") {
    return {
      label: demoMode ? "Demo Recording" : "Recording",
      description: demoMode
        ? "데모 화면에서 흐름만 미리 확인하고 있습니다."
        : "핵심 경험, 결과, 배운 점 순서로 또렷하게 답변해보세요.",
    };
  }

  if (phase === "uploading") {
    return {
      label: "Uploading",
      description: "답변을 업로드하고 다음 질문 또는 결과 페이지를 준비하고 있습니다.",
    };
  }

  return {
    label: "Needs Attention",
    description: errorMessage ?? "마이크 권한 또는 네트워크 상태를 다시 확인해주세요.",
  };
}
