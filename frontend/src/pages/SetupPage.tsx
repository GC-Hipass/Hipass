import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiClientError } from "../api/client";
import { interviewApi } from "../api/interview";
import type { Company, Difficulty, JobRole } from "../api/types";
import { useDeviceCheck } from "../hooks/useDeviceCheck";
import styles from "./SetupPage.module.css";

const COMPANY_OPTIONS: { value: Company; label: string }[] = [
  { value: "naver", label: "NAVER" },
  { value: "sk", label: "SK" },
  { value: "samsung", label: "SAMSUNG" },
];

const DIFFICULTY_OPTIONS: { value: Difficulty; label: string }[] = [
  { value: "easy", label: "Easy" },
  { value: "normal", label: "Normal" },
  { value: "hard", label: "Hard" },
];

const JOB_OPTIONS: { value: JobRole; label: string }[] = [
  { value: "app", label: "App" },
  { value: "web", label: "Web" },
  { value: "ai", label: "AI" },
  { value: "devops", label: "DevOps" },
];

const COMPANY_LABELS: Record<Company, string> = {
  naver: "NAVER",
  sk: "SK",
  samsung: "SAMSUNG",
};

const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  easy: "Easy",
  normal: "Normal",
  hard: "Hard",
};

const JOB_LABELS: Record<JobRole, string> = {
  app: "App",
  web: "Web",
  ai: "AI",
  devops: "DevOps",
};

const MAX_FILE_MB = 50;

export default function SetupPage() {
  const navigate = useNavigate();
  const deviceCheck = useDeviceCheck();
  const [submitting, setSubmitting] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [company, setCompany] = useState<Company>("naver");
  const [difficulty, setDifficulty] = useState<Difficulty>("normal");
  const [jobRole, setJobRole] = useState<JobRole>("web");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const canProceed = useMemo(
    () =>
      Boolean(company) &&
      Boolean(difficulty) &&
      Boolean(jobRole) &&
      deviceCheck.micActive,
    [company, difficulty, deviceCheck.micActive, jobRole],
  );

  function onPickFile(input: HTMLInputElement) {
    const picked = input.files?.[0];
    if (!picked) return;
    const ext = picked.name.toLowerCase().split(".").pop();
    if (!ext || !["pdf", "docx", "txt"].includes(ext)) {
      setErrorMessage("PDF, DOCX, TXT 파일만 업로드할 수 있습니다.");
      input.value = "";
      return;
    }
    if (picked.size > MAX_FILE_MB * 1024 * 1024) {
      setErrorMessage(`파일 크기는 ${MAX_FILE_MB}MB 이하만 가능합니다.`);
      input.value = "";
      return;
    }
    setErrorMessage(null);
    setFile(picked);
  }

  async function checkDevices() {
    deviceCheck.release();
    await deviceCheck.request();
  }

  async function startInterview() {
    if (!deviceCheck.micActive) {
      setErrorMessage("면접을 시작하려면 마이크 권한을 허용해주세요.");
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    try {
      const res = await interviewApi.upload({ file, company, difficulty, jobRole });
      navigate(`/interview/${res.session_id}/1`, {
        state: { questionCount: res.question_count, recordingSeconds: res.recording_seconds },
      });
    } catch (e) {
      const message =
        e instanceof ApiClientError ? `${e.code}: ${e.message}` : (e as Error).message;
      setErrorMessage(message);
      setSubmitting(false);
    }
  }

  function previewMockResult() {
    navigate("/mock/result");
  }

  const inputRef = useRef<HTMLInputElement | null>(null);
  const microphoneWidth = Math.max(6, Math.round(deviceCheck.audioLevel * 100));
  const footerMessage = submitting
    ? "문서를 업로드하고 첫 질문을 준비하고 있어요."
    : !deviceCheck.micActive
        ? "시작 전에 마이크 권한을 연결해주세요."
        : file
          ? "문서와 마이크가 준비됐어요. 바로 면접을 시작할 수 있습니다."
          : "문서 없이도 시작할 수 있어요. 바로 면접을 진행해보세요.";

  return (
    <div className={styles.page}>
      <div className={styles.backdrop} aria-hidden />

      <header className={styles.header}>
        <button className={styles.back} type="button" aria-label="뒤로 가기" disabled>
          ‹
        </button>
        <span className={styles.title}>AI 모의면접</span>
        <span className={styles.stepBadge}>1 / 1</span>
      </header>

      <main className={styles.main}>
        <section className={styles.introPanel}>
          <div className={styles.hero}>
            <span className={styles.eyebrow}>AI 모의면접</span>
            <h1 className={styles.heroTitle}>
              문서가 없어도
              <br />
              바로 면접을 시작하세요
            </h1>
            <p className={styles.heroSub}>
              문서를 첨부하면 질문이 더 구체적으로 맞춰지고, 첨부하지 않아도 기본 면접 흐름으로
              바로 시작할 수 있습니다.
            </p>
          </div>

          <div className={styles.heroHighlights}>
            <article className={styles.highlightCard}>
              <span className={styles.highlightLabel}>문서 첨부</span>
              <strong className={styles.highlightValue}>선택 사항</strong>
            </article>
            <article className={styles.highlightCard}>
              <span className={styles.highlightLabel}>답변 타이머</span>
              <strong className={styles.highlightValue}>문항당 30초</strong>
            </article>
            <article className={styles.highlightCard}>
              <span className={styles.highlightLabel}>결과 리포트</span>
              <strong className={styles.highlightValue}>강점·보완점 분석</strong>
            </article>
          </div>
        </section>

        <section className={styles.workspace}>
          <div className={styles.primaryPanel}>
            <header className={styles.sectionHeader}>
              <div>
                <span className={styles.sectionEyebrow}>면접 설정</span>
                <h2 className={styles.sectionTitle}>면접 정보 설정</h2>
              </div>
              <p className={styles.sectionDescription}>
                기업, 난이도, 직무를 고르면 바로 면접을 시작할 수 있습니다.
              </p>
            </header>

            <div
              className={styles.dropzone}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
              }}
              role="button"
              tabIndex={0}
              aria-label="파일 첨부"
            >
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.docx,.txt,application/pdf"
                className={styles.fileInput}
                onChange={(e) => onPickFile(e.currentTarget)}
              />

              {!file ? (
                <>
                  <div className={styles.dropIcon} aria-hidden>⬆</div>
                  <div className={styles.dropBody}>
                    <div className={styles.dropTitle}>문서가 있다면 함께 첨부해주세요</div>
                    <div className={styles.dropSub}>
                      이력서, 경력기술서, 포트폴리오를 올리면 질문이 더 구체적으로 맞춰집니다.
                    </div>
                  </div>
                  <div className={styles.dropMeta}>
                    PDF · DOCX · TXT · 최대 {MAX_FILE_MB}MB · 첨부 선택
                  </div>
                  <button className={styles.btnPrimaryGhost} type="button">
                    파일 선택
                  </button>
                </>
              ) : (
                <div className={styles.fileChip}>
                  <span className={styles.fileChipName}>{file.name}</span>
                  <span className={styles.fileChipSize}>
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </span>
                  <button
                    className={styles.fileChipClear}
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (inputRef.current) inputRef.current.value = "";
                      setFile(null);
                    }}
                  >
                    ×
                  </button>
                </div>
              )}
            </div>

            {errorMessage && <div className={styles.error}>{errorMessage}</div>}

            <section className={styles.options}>
              <OptionGroup
                label="기업"
                value={company}
                options={COMPANY_OPTIONS}
                onChange={setCompany}
              />
              <OptionGroup
                label="난이도"
                value={difficulty}
                options={DIFFICULTY_OPTIONS}
                onChange={setDifficulty}
              />
              <OptionGroup
                label="직무"
                value={jobRole}
                options={JOB_OPTIONS}
                onChange={setJobRole}
              />
            </section>
          </div>

          <aside className={styles.secondaryPanel}>
            <section className={styles.deviceCard}>
              <header className={styles.sectionHeader}>
                <div>
                  <span className={styles.sectionEyebrow}>장치 확인</span>
                  <h2 className={styles.sectionTitle}>장치 상태 확인</h2>
                </div>
                <button
                  className={styles.deviceAction}
                  type="button"
                  onClick={() => void checkDevices()}
                >
                  {deviceCheck.micActive || deviceCheck.cameraActive ? "다시 확인" : "권한 연결"}
                </button>
              </header>

              <p className={styles.sectionDescription}>
                마이크는 필수입니다. 카메라는 선택 사항이며 연결되면 바로 프리뷰를 볼 수 있어요.
              </p>

              <div className={styles.videoFrame}>
                {deviceCheck.cameraActive ? (
                  <video
                    ref={deviceCheck.attachVideo}
                    className={styles.video}
                    playsInline
                    muted
                    autoPlay
                  />
                ) : (
                  <>
                    <div className={styles.videoGlow} aria-hidden />
                    <div className={styles.videoEmpty}>카메라 대기</div>
                    <p className={styles.videoHint}>
                      카메라가 연결되면 이 영역에서 프리뷰를 볼 수 있습니다.
                    </p>
                  </>
                )}
              </div>

              <div className={styles.deviceMeters}>
                <div
                  className={`${styles.deviceBadge} ${
                    deviceCheck.micActive ? styles.deviceBadgeOk : ""
                  }`}
                >
                  <span>마이크</span>
                  <div className={styles.levelBar}>
                    <span className={styles.levelFill} style={{ width: `${microphoneWidth}%` }} />
                  </div>
                </div>
                <div
                  className={`${styles.deviceBadge} ${
                    deviceCheck.cameraActive ? styles.deviceBadgeOk : ""
                  }`}
                >
                  <span>{deviceCheck.cameraActive ? "카메라 연결됨" : "카메라는 선택 사항"}</span>
                </div>
              </div>

              {deviceCheck.error && <div className={styles.deviceError}>{deviceCheck.error}</div>}
            </section>

            <section className={styles.readinessCard}>
              <header className={styles.sectionHeader}>
                <div>
                  <span className={styles.sectionEyebrow}>시작 전 확인</span>
                  <h2 className={styles.sectionTitle}>시작 전 요약</h2>
                </div>
              </header>

              <div className={styles.readinessList}>
                <div className={`${styles.readinessItem} ${file ? styles.readinessItemDone : ""}`}>
                  <div className={styles.readinessItemMeta}>
                    <span className={styles.readinessLabel}>문서</span>
                    <strong className={styles.readinessValue}>
                      {file ? file.name : "첨부 없이 기본 질문으로 진행"}
                    </strong>
                  </div>
                </div>

                <div
                  className={`${styles.readinessItem} ${
                    deviceCheck.micActive ? styles.readinessItemDone : ""
                  }`}
                >
                  <div className={styles.readinessItemMeta}>
                    <span className={styles.readinessLabel}>장치</span>
                    <strong className={styles.readinessValue}>
                      {deviceCheck.micActive ? "마이크 준비 완료" : "마이크 권한 필요"}
                    </strong>
                  </div>
                </div>

                <div className={`${styles.readinessItem} ${styles.readinessItemDone}`}>
                  <div className={styles.readinessItemMeta}>
                    <span className={styles.readinessLabel}>면접 설정</span>
                    <strong className={styles.readinessValue}>
                      {COMPANY_LABELS[company]} · {JOB_LABELS[jobRole]} ·{" "}
                      {DIFFICULTY_LABELS[difficulty]}
                    </strong>
                  </div>
                </div>
              </div>
            </section>
          </aside>
        </section>

        <footer className={styles.footer}>
          <div className={styles.footerCopy}>
            <span className={styles.footerLabel}>상태</span>
            <p className={styles.footerText}>{footerMessage}</p>
          </div>

          <div className={styles.footerActions}>
            <button className={styles.btnSecondary} type="button" onClick={previewMockResult}>
              결과 화면 미리보기
            </button>
            <button
              className={styles.btnPrimary}
              type="button"
              disabled={!canProceed || submitting}
              onClick={() => void startInterview()}
            >
              {submitting ? "면접 준비 중..." : "면접 시작"}
            </button>
          </div>
        </footer>
      </main>
    </div>
  );
}

interface OptionGroupProps<T extends string> {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}

function OptionGroup<T extends string>({ label, value, options, onChange }: OptionGroupProps<T>) {
  return (
    <div className={styles.optionGroup}>
      <div className={styles.optionLabel}>{label}</div>
      <div className={styles.optionRow}>
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={`${styles.optionChip} ${value === opt.value ? styles.optionChipActive : ""}`}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
