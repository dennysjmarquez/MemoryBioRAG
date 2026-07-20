import styles from './RepairCard.module.css'

interface RepairItem {
  label: string
  meta: string
  raw: unknown
}

interface RepairCardProps {
  icon: string
  title: string
  total: number
  count: number
  items: RepairItem[]
  actionLabel: string
  infoTooltip?: string
  loadingKey: string | null
  onAction: (item: RepairItem) => void
  onClear?: () => void
  clearing?: boolean
}

const RepairCard = ({ icon, title, total, count, items, actionLabel, infoTooltip, loadingKey, onAction, onClear, clearing }: RepairCardProps) => {
  if (count === 0) {
    return (
      <div className={styles.card}>
        <div className={styles.header}>
          <span className={styles.icon}>{icon}</span>
          <span className={styles.title}>{title}</span>
          <span className={styles.badge}>0</span>
        </div>
        <div className={styles.empty}>Todo bien - nada que reparar</div>
      </div>
    )
  }

  return (
    <div className={`${styles.card} ${styles.hasItems}`}>
      <div className={styles.header}>
        <span className={styles.icon}>{icon}</span>
        <span className={styles.title}>{title}</span>
        {infoTooltip && (
          <span className={styles.infoIcon} title={infoTooltip}>ⓘ</span>
        )}
        <span className={`${styles.badge} ${styles.badgeWarn}`}>
          {count}{total > count ? `/${total}` : ''}
        </span>
      </div>
      <ul className={styles.list}>
        {items.map((item, i) => {
          const isLoading = loadingKey === item.label
          return (
            <li key={item.label + i} className={styles.listItem}>
              <div className={styles.itemInfo}>
                <span className={styles.itemLabel}>{item.label}</span>
                <span className={styles.itemMeta}>{item.meta}</span>
              </div>
              <button
                className={`${styles.actionBtn} ${isLoading ? styles.loading : ''}`}
                onClick={() => onAction(item)}
                disabled={isLoading}
              >
                {isLoading ? '...' : actionLabel}
              </button>
            </li>
          )
        })}
      </ul>
      {onClear && (
        <div className={styles.footer}>
          <button
            className={styles.clearBtn}
            onClick={onClear}
            disabled={clearing}
          >
            {clearing ? 'Limpiando...' : '🗑️ Limpiar historial (>7 días)'}
          </button>
        </div>
      )}
    </div>
  )
}

export default RepairCard
export type { RepairItem }
