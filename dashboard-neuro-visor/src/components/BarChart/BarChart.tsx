import styles from "./BarChart.module.css";

interface BarChartProps {
  title: string;
  data: Array<{ label: string; value: number; color?: string }>;
  maxBars?: number;
  showValue?: boolean;
  unit?: string;
}

const BarChart = ({
  title,
  data,
  maxBars = 10,
  showValue = true,
  unit = "",
}: BarChartProps) => {
  const sorted = [...data].sort((a, b) => b.value - a.value).slice(0, maxBars);
  const maxValue = Math.max(...sorted.map((d) => d.value), 1);

  return (
    <div className={styles.bars} role="list" aria-label={title}>
      {sorted.map((item, index) => (
        <div
          key={`${item.label}-${index}`}
          className={styles.barRow}
          role="listitem"
        >
          <div className={styles.barWrapper}>
            <span className={styles.label} title={item.label}>
              {item.label}
            </span>
            <div className={styles.barTrack}>
              <div
                className={styles.barFill}
                style={{
                  width: `${(item.value / maxValue) * 100}%`,
                  backgroundColor: item.color || "var(--accent-color)",
                }}
              />
            </div>
          </div>
          {showValue && (
            <span className={styles.value}>
              {item.value.toLocaleString()}
              {unit && ` ${unit}`}
            </span>
          )}
        </div>
      ))}
    </div>
  );
};

export default BarChart;
