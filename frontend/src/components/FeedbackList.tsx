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
      {items.map((it) => (
        <li key={it.question_id} className={styles.item}>
          <header className={styles.itemHeader}>
            <span className={styles.order}>Q{it.order}</span>
            <span className={styles.score}>{it.score}점</span>
          </header>
          <p className={styles.question}>{it.question}</p>
          <p className={styles.answer}>
            <span className={styles.aLabel}>나의 답변</span>
            {it.answer || "(녹음된 답변이 없습니다)"}
          </p>
          {it.feedback && <p className={styles.feedback}>💬 {it.feedback}</p>}
        </li>
      ))}
    </ol>
  );
}
