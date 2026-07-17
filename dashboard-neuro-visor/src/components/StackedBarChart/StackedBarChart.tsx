import styles from "./StackedBarChart.module.css";

interface StackedBarChartProps {
  title: string;
  data: Array<{
    label: string;
    activos: number;
    dormidos: number;
    total: number;
    color?: string;
  }>;
  maxBars?: number;
}

const StackedBarChart = ({
  title,
  data,
  maxBars = 12,
}: StackedBarChartProps) => {
  const sorted = [...data]
    .sort((a, b) => b.total - a.total)
    .slice(0, maxBars);
  const maxValue = Math.max(...sorted.map((d) => d.total), 1);

  const dormantCategories = sorted.filter(
    (d) => d.activos === 0 && d.dormidos > 0
  );

  return (
    <div className={styles.container}>
      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={styles.legendDotActive} /> Activos
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDotDormant} /> Dormidos
        </span>
      </div>

      <div className={styles.bars} role="list" aria-label={title}>
        {sorted.map((item, index) => {
          const activeWidth = (item.activos / maxValue) * 100;
          const dormantWidth = (item.dormidos / maxValue) * 100;

          return (
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
                    className={styles.barFillActive}
                    style={{
                      width: `${activeWidth}%`,
                      backgroundColor: item.color || "var(--accent-color)",
                    }}
                  />
                  <div
                    className={styles.barFillDormant}
                    style={{
                      width: `${dormantWidth}%`,
                      backgroundColor: item.color || "var(--accent-color)",
                    }}
                  />
                </div>
              </div>
              <span
                className={styles.value}
                title={`${item.activos} activos, ${item.dormidos} dormidos`}
              >
                {item.activos}/{item.dormidos}
              </span>
            </div>
          );
        })}
      </div>

      {dormantCategories.length > 0 && (
        <div className={styles.alert}>
          <span className={styles.alertIcon}>!</span>
          <span className={styles.alertText}>
            {dormantCategories.length} categorías 100% dormidas:{" "}
            {dormantCategories.map((d) => d.label).join(", ")}
          </span>
        </div>
      )}
    </div>
  );
};

export default StackedBarChart;
