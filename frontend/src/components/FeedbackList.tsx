import type { QAItem } from "../api/types";
import styles from "./FeedbackList.module.css";

interface FeedbackListProps {
  items: QAItem[];
}

export default function FeedbackList({ items }: FeedbackListProps) {
  if (items.length === 0) {
    return <p className={styles.empty}>문항별 결과가 없습니다.</p>;
  }

  return (
    <ol className={styles.list}>
      {items.map((it) => {
        const tone = getScoreTone(it.score);

        return (
          <li key={it.question_id} className={`${styles.item} ${tone.cardClass}`}>
            <header className={styles.itemHeader}>
              <div className={styles.itemMeta}>
                <span className={styles.order}>Question {it.order}</span>
                <p className={styles.question}>{it.question}</p>
              </div>
              <span className={`${styles.score} ${tone.scoreClass}`}>{it.score}점</span>
            </header>

            <p className={styles.answer}>
              <span className={styles.aLabel}>나의 답변</span>
              {it.answer || "(녹음된 답변이 없습니다)"}
            </p>

            <div className={styles.feedback}>
              <span className={styles.aLabel}>AI 피드백</span>
              {it.feedback || "아직 생성된 피드백이 없습니다."}
            </div>

            <span className={styles.scoreHint}>{tone.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function getScoreTone(score: number): {
  label: string;
  cardClass: string;
  scoreClass: string;
} {
  if (score >= 85) {
    return {
      label: "강하게 어필된 답변",
      cardClass: styles.itemGood,
      scoreClass: styles.scoreGood,
    };
  }

  if (score >= 70) {
    return {
      label: "안정적으로 전달된 답변",
      cardClass: styles.itemSteady,
      scoreClass: styles.scoreSteady,
    };
  }

  return {
    label: "보완이 필요한 답변",
    cardClass: styles.itemCaution,
    scoreClass: styles.scoreCaution,
  };
}
