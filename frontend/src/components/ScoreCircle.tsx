import styles from "./ScoreCircle.module.css";

interface ScoreCircleProps {
  /** 0~100 점수 */
  score: number;
  /** A/B/C/D/F 등 등급 */
  grade: string;
}

const SIZE = 180;
const STROKE = 14;
const RADIUS = (SIZE - STROKE) / 2;
const CIRC = 2 * Math.PI * RADIUS;

export default function ScoreCircle({ score, grade }: ScoreCircleProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const offset = CIRC * (1 - clamped / 100);

  return (
    <div className={styles.wrap} style={{ width: SIZE, height: SIZE }}>
      <svg width={SIZE} height={SIZE} className={styles.svg}>
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          stroke="rgba(255,255,255,0.18)"
          strokeWidth={STROKE}
          fill="none"
        />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          stroke="url(#scoreGrad)"
          strokeWidth={STROKE}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={CIRC}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
        <defs>
          <linearGradient id="scoreGrad" x1="0%" y1="0%" x2="100%" y2="100%">
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
