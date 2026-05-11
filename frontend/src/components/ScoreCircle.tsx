import { useId } from "react";

import styles from "./ScoreCircle.module.css";

interface ScoreCircleProps {
  /** 0~100 점수 */
  score: number;
  /** A/B/C/D/F 등 등급 */
  grade: string;
  size?: number;
}

export default function ScoreCircle({ score, grade, size = 180 }: ScoreCircleProps) {
  const gradientId = useId();
  const clamped = Math.max(0, Math.min(100, score));
  const stroke = Math.max(12, Math.round(size * 0.078));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className={styles.wrap} style={{ width: size, height: size }}>
      <svg width={size} height={size} className={styles.svg}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgba(255,255,255,0.18)"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={`url(#${gradientId})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#a8bbff" />
            <stop offset="100%" stopColor="#ffffff" />
          </linearGradient>
        </defs>
      </svg>

      <div className={styles.center}>
        <div className={styles.score}>
          <span className={styles.scoreNum}>{clamped}</span>
          <span className={styles.scoreUnit}>점</span>
        </div>
        <div className={styles.grade}>{grade}</div>
      </div>
    </div>
  );
}
