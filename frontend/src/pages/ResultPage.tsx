import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { ApiClientError } from "../api/client";
import type { EvaluationResultResponse } from "../api/types";
import FeedbackList from "../components/FeedbackList";
import ScoreCircle from "../components/ScoreCircle";
import { interviewApi } from "../api/interview";
import { buildDemoResult, isDemoMode } from "../mocks/interviewDemo";
import styles from "./ResultPage.module.css";

export default function ResultPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const demoMode = isDemoMode(location.search);
  const sessionIdNum = Number(sessionId);

  const [result, setResult] = useState<EvaluationResultResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    if (demoMode) {
      setResult(buildDemoResult(sessionIdNum));
      setErrorMessage(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }

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
  }, [demoMode, sessionIdNum]);

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

  const averageScore =
    qa_list.length === 0
      ? total_score
      : Math.round(qa_list.reduce((sum, item) => sum + item.score, 0) / qa_list.length);

  const bestItem =
    qa_list.length === 0
      ? null
      : qa_list.reduce((best, item) => (item.score > best.score ? item : best), qa_list[0]);

  const weakestItem =
    qa_list.length === 0
      ? null
      : qa_list.reduce((best, item) => (item.score < best.score ? item : best), qa_list[0]);

  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <div className={styles.heroBg} aria-hidden />
        <div className={styles.heroContent}>
          <div className={styles.heroCopy}>
            <span className={styles.heroLabel}>면접 결과</span>
            <h1 className={styles.heroTitle}>{analysis.summary || "면접을 완료하셨습니다."}</h1>
            <p className={styles.heroSub}>
              총 {qa_list.length}개 문항을 분석해 답변 패턴과 다음 면접에서 살릴 포인트를
              정리했습니다.
            </p>

            <div className={styles.heroStats}>
              <SummaryStat label="종합 평가" value={getPerformanceLabel(total_score)} />
              <SummaryStat label="분석 문항" value={`${qa_list.length}개`} />
              <SummaryStat label="평균 점수" value={`${averageScore}점`} />
            </div>
          </div>

          <div className={styles.heroScore}>
            <ScoreCircle score={total_score} grade={grade} size={196} />
            <span className={styles.heroScoreCaption}>현재 면접 완성도</span>
          </div>
        </div>
      </header>

      <main className={styles.main}>
        <section className={styles.overviewColumn}>
          <section className={styles.cardGrid}>
            <FeedbackCard
              kind="strengths"
              title="잘한 점"
              items={analysis.strengths}
              emptyText="기록된 강점이 없습니다."
            />
            <FeedbackCard
              kind="weaknesses"
              title="보완 포인트"
              items={analysis.weaknesses}
              emptyText="특별히 부족한 점이 없습니다."
            />
          </section>

          <section className={styles.spotlightGrid}>
            <SpotlightCard
              tone="good"
              label="가장 좋은 답변"
              title={bestItem ? `Q${bestItem.order} · ${bestItem.score}점` : "기록 없음"}
              description={bestItem?.question ?? "아직 분석된 문항이 없습니다."}
            />
            <SpotlightCard
              tone="caution"
              label="보완이 필요한 답변"
              title={weakestItem ? `Q${weakestItem.order} · ${weakestItem.score}점` : "기록 없음"}
              description={weakestItem?.question ?? "아직 분석된 문항이 없습니다."}
            />
          </section>

          <section className={styles.tipBox}>
            <div className={styles.tipHeader}>
              <span className={styles.tipBadge}>다음 준비</span>
              <h2 className={styles.tipTitle}>다음 면접에서 바로 써먹을 포인트</h2>
            </div>
            <p className={styles.tipText}>
              {analysis.recommendation || "다음 면접에서도 좋은 결과가 있길 응원합니다."}
            </p>
          </section>
        </section>

        <section className={styles.qaPanel}>
          <header className={styles.qaHeader}>
            <div>
              <span className={styles.qaEyebrow}>문항 리뷰</span>
              <h2 className={styles.qaTitle}>문항별 결과</h2>
            </div>
            <span className={styles.qaCount}>{qa_list.length}개 답변 분석 완료</span>
          </header>
          <FeedbackList items={qa_list} />
        </section>
      </main>

      <div className={styles.footerActions}>
        <Link to="/" className={styles.primaryLink}>
          새 면접 시작하기
        </Link>
      </div>
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
        <span className={styles.cardIconWrap} aria-hidden>
          <span className={styles.cardIcon}>{kind === "strengths" ? "✦" : "▲"}</span>
        </span>
        <div>
          <h3 className={styles.cardTitle}>{title}</h3>
          <p className={styles.cardSub}>
            {kind === "strengths"
              ? "답변에서 잘 드러난 강점을 모았습니다."
              : "다음 면접에서 보완하면 좋은 지점을 정리했습니다."}
          </p>
        </div>
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

interface SummaryStatProps {
  label: string;
  value: string;
}

function SummaryStat({ label, value }: SummaryStatProps) {
  return (
    <article className={styles.heroStat}>
      <span className={styles.heroStatLabel}>{label}</span>
      <strong className={styles.heroStatValue}>{value}</strong>
    </article>
  );
}

interface SpotlightCardProps {
  tone: "good" | "caution";
  label: string;
  title: string;
  description: string;
}

function SpotlightCard({ tone, label, title, description }: SpotlightCardProps) {
  return (
    <article
      className={`${styles.spotlightCard} ${
        tone === "good" ? styles.spotlightGood : styles.spotlightCaution
      }`}
    >
      <span className={styles.spotlightLabel}>{label}</span>
      <h3 className={styles.spotlightTitle}>{title}</h3>
      <p className={styles.spotlightText}>{description}</p>
    </article>
  );
}

function getPerformanceLabel(score: number): string {
  if (score >= 90) return "매우 강한 인상";
  if (score >= 80) return "전달력 우수";
  if (score >= 70) return "안정적인 답변";
  return "추가 보완 필요";
}
