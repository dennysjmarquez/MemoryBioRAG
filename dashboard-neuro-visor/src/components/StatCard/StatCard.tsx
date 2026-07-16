import styles from './StatCard.module.css'

interface StatCardProps {
  label: string
  value: string | number
  accent?: boolean
  subLabel?: string
  description?: string
  progress?: number
  progressLabel?: string
}

const StatCard = ({ label, value, accent, subLabel, description, progress, progressLabel }: StatCardProps) => (
  <div className={`${styles.card} ${accent ? styles.accent : ''}`}>
    <span className={styles.value}>{value}</span>
    <span className={styles.label}>{label}</span>
    {subLabel && <span className={styles.subLabel}>{subLabel}</span>}
    {description && <span className={styles.description}>{description}</span>}
    {progress !== undefined && (
      <div className={styles.progressWrapper}>
        <div
          className={styles.progressBar}
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
    )}
    {progressLabel && <span className={styles.progressLabel}>{progressLabel}</span>}
  </div>
)

export default StatCard