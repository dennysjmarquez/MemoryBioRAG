import styles from './StatCard.module.css'

interface StatCardProps {
  label: string
  value: string | number
  icon?: string
  accent?: boolean
  color?: 'blue' | 'green' | 'yellow' | 'purple' | 'cyan' | 'red'
  subLabel?: string
  description?: string
  progress?: number
  progressLabel?: string
  maxValue?: number
}

const StatCard = ({
  label,
  value,
  icon,
  accent,
  color = 'blue',
  subLabel,
  description,
  progress,
  progressLabel,
  maxValue,
}: StatCardProps) => {
  const progressColor = accent
    ? 'var(--accent-color)'
    : `var(--stat-${color})`

  return (
    <div className={`${styles.card} ${accent ? styles.accent : ''} ${styles[color]}`}>
      <div className={styles.header}>
        {icon && <span className={styles.icon}>{icon}</span>}
        <span className={styles.label}>{label}</span>
      </div>
      <div className={styles.valueRow}>
        <span className={styles.value}>{value}</span>
        {maxValue !== undefined && (
          <span className={styles.maxValue}>/ {maxValue.toLocaleString()}</span>
        )}
      </div>
      {subLabel && <span className={styles.subLabel}>{subLabel}</span>}
      {description && <span className={styles.description}>{description}</span>}
      {progress !== undefined && (
        <div className={styles.progressWrapper}>
          <div
            className={styles.progressBar}
            style={{
              width: `${Math.min(100, Math.max(0, progress))}%`,
              backgroundColor: progressColor,
            }}
          />
        </div>
      )}
      {progressLabel && <span className={styles.progressLabel}>{progressLabel}</span>}
    </div>
  )
}

export default StatCard
