import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { interviewApi } from "../api/interview";
import { ApiClientError } from "../api/client";
import type { Company, Difficulty, JobRole } from "../api/types";
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

const MAX_FILE_MB = 50;

export default function SetupPage() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [company, setCompany] = useState<Company>("naver");
  const [difficulty, setDifficulty] = useState<Difficulty>("normal");
  const [jobRole, setJobRole] = useState<JobRole>("web");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const canProceed = useMemo(
    () => Boolean(company) && Boolean(difficulty) && Boolean(jobRole),
    [company, difficulty, jobRole],
  );

  function onPickFile(input: HTMLInputElement) {
    const picked = input.files?.[0];
    if (!picked) return;
    if (!picked.name.toLowerCase().endsWith(".pdf")) {
      setErrorMessage("PDF 파일만 업로드할 수 있습니다.");
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

  async function startInterview() {
    if (!file) return;
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

  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button className={styles.back} type="button" aria-label="뒤로 가기" disabled>
          ‹
        </button>
        <span className={styles.title}>AI 모의면접</span>
        <span className={styles.stepBadge}>1 / 1</span>
      </header>

      <main className={styles.main}>
        <section className={styles.hero}>
          <h1>면접 질문을 위해<br />서류를 추가해주세요</h1>
          <p className={styles.heroSub}>경력기술서나 자기소개서가 있다면 첨부하세요.</p>
        </section>

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
            accept=".pdf,application/pdf"
            className={styles.fileInput}
            onChange={(e) => onPickFile(e.currentTarget)}
          />

          {!file ? (
            <>
              <div className={styles.dropIcon} aria-hidden>⬆</div>
              <div className={styles.dropTitle}>PDF 파일을 첨부해주세요</div>
              <div className={styles.dropSub}>pdf만 가능 · 최대 {MAX_FILE_MB}MB</div>
              <button className={styles.btnPrimaryGhost} type="button">
                파일 첨부
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

        <footer className={styles.footer}>
          <button
            className={styles.btnPrimary}
            type="button"
            disabled={!canProceed || submitting}
            onClick={() => void startInterview()}
          >
            {submitting ? "면접 준비 중..." : "면접 시작"}
          </button>
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
