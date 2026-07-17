import styles from "./BarChart.module.css";

interface BarChartProps {
  title: string;
  data: Array<{
    label: string;
    value: number;
    color?: string;
    eje?: string;
    valor?: string;
  }>;
  maxBars?: number;
  showValue?: boolean;
  showColumns?: boolean;
  unit?: string;
}

const BarChart = ({
  title,
  data,
  maxBars = 10,
  showValue = true,
  showColumns = false,
  unit = "",
}: BarChartProps) => {
  const sorted = [...data].sort((a, b) => b.value - a.value).slice(0, maxBars);
  const maxValue = Math.max(...sorted.map((d) => d.value), 1);

  if (showColumns) {
    return (
      <div className={styles.columnsContainer} role="list" aria-label={title}>
        <div className={styles.columnsHeader}>
          <span className={styles.columnEje}>Dimensión</span>
          <span className={styles.columnValor}>Valor</span>
          <span className={styles.columnBar}></span>
          <span className={styles.columnCount}>Count</span>
        </div>
        {sorted.map((item, index) => (
          <div
            key={`${item.label}-${index}`}
            className={styles.columnRow}
            role="listitem"
          >
            <span className={styles.columnEje} title={item.eje}>
              {item.eje || item.label.split('.')[0]}
            </span>
            <span className={styles.columnValor} title={item.valor}>
              {item.valor || item.label.split('.')[1] || item.label}
            </span>
            <div className={styles.columnBarTrack}>
              <div
                className={styles.columnBarFill}
                style={{
                  width: `${(item.value / maxValue) * 100}%`,
                  backgroundColor: item.color || "var(--accent-color)",
                }}
              />
            </div>
            <span className={styles.columnCount}>
              {item.value.toLocaleString()}{unit}
            </span>
          </div>
        ))}
      </div>
    );
  }

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
