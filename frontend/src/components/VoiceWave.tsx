import styles from "./VoiceWave.module.css";

interface VoiceWaveProps {
  active: boolean;
  /** 0~1 실시간 음성 입력 레벨 */
  level: number;
}

const BAR_COUNT = 24;

/** 음성 입력 레벨에 반응하는 막대 시각화. 텍스트 없이 UI 만으로 답변 중을 표시. */
export default function VoiceWave({ active, level }: VoiceWaveProps) {
  return (
    <div className={`${styles.wrap} ${active ? styles.wrapActive : ""}`} aria-hidden>
      {Array.from({ length: BAR_COUNT }).map((_, i) => {
        // 중앙이 가장 크게, 가장자리가 작게
        const distFromCenter = Math.abs(i - BAR_COUNT / 2) / (BAR_COUNT / 2);
        const baseHeight = 12 + (1 - distFromCenter) * 28;
        const reactive = active ? baseHeight + level * 38 * (1 - distFromCenter * 0.5) : 6;
        return (
          <span
            key={i}
            className={styles.bar}
            style={{
              height: `${Math.max(4, reactive)}px`,
              animationDelay: `${i * 0.04}s`,
            }}
          />
        );
      })}
    </div>
  );
}
