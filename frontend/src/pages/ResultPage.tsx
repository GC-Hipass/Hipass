import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiClientError } from "../api/client";
import { interviewApi } from "../api/interview";
import type { EvaluationResultResponse } from "../api/types";
import ScoreCircle from "../components/ScoreCircle";
import FeedbackList from "../components/FeedbackList";
import styles from "./ResultPage.module.css";

export default function ResultPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const sessionIdNum = Number(sessionId);

  const [result, setResult] = useState<EvaluationResultResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    interviewApi
      .getResult(sessionIdNum)
      .then((res) => {
        if (!cancelled) setResult(res);
      })
      .catch((e) => {
        if (cancelled) return;
        const msg =
          e instanceof ApiClientError ? `${e.code}: ${e.message}` : (e as Error).message;
        setErrorMessage(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionIdNum]);

  if (loading) {
    return (
      <div className={styles.loading}>
        <span>결과를 불러오는 중...</span>
      </div>
    );
  }

  if (errorMessage || !result) {
    return (
      <div className={styles.loading}>
        <span>{errorMessage ?? "결과를 불러올 수 없습니다."}</span>
        <button className={styles.retryBtn} type="button" onClick={() => navigate("/")}>
          처음으로
        </button>
      </div>
    );
  }

  const { total_score, grade, qa_list, analysis } = result;

  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <div className={styles.heroBg} aria-hidden />
        <div className={styles.heroContent}>
          <span className={styles.heroLabel}>총평</span>
          <ScoreCircle score={total_score} grade={grade} />
          <h1 className={styles.heroTitle}>
            {analysis.summary || "면접을 완료하셨습니다."}
          </h1>
        </div>
      </header>

      <main className={styles.main}>
        <section className={styles.cardGrid}>
          <FeedbackCard
            kind="strengths"
            title="잘한 점"
            items={analysis.strengths}
            emptyText="기록된 강점이 없습니다."
          />
          <FeedbackCard
            kind="weaknesses"
            title="부족한 점"
            items={analysis.weaknesses}
            emptyText="특별히 부족한 점이 없습니다."
          />
        </section>

        <section className={styles.tipBox}>
          <span className={styles.tipBadge}>개선 팁</span>
          <p className={styles.tipText}>
            {analysis.recommendation || "다음 면접에서도 좋은 결과가 있길 응원합니다."}
          </p>
        </section>

        <section className={styles.qaBox}>
          <h2 className={styles.qaTitle}>문항별 결과</h2>
          <FeedbackList items={qa_list} />
        </section>

        <div className={styles.footerActions}>
          <Link to="/" className={styles.primaryLink}>
            새 면접 시작하기
          </Link>
        </div>
      </main>
    </div>
  );
}

interface FeedbackCardProps {
  kind: "strengths" | "weaknesses";
  title: string;
  items: string[];
  emptyText: string;
}

function FeedbackCard({ kind, title, items, emptyText }: FeedbackCardProps) {
  return (
    <article className={`${styles.card} ${kind === "strengths" ? styles.cardGood : styles.cardBad}`}>
      <header className={styles.cardHeader}>
        <span className={styles.cardIcon} aria-hidden>
          {kind === "strengths" ? "✦" : "▲"}
        </span>
        <h3 className={styles.cardTitle}>{title}</h3>
      </header>
      {items.length === 0 ? (
        <p className={styles.cardEmpty}>{emptyText}</p>
      ) : (
        <ul className={styles.cardList}>
          {items.map((it, idx) => (
            <li key={idx}>{it}</li>
          ))}
        </ul>
      )}
    </article>
  );
}
