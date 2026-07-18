import styles from './NodeIdentityPanel.module.css'
import type { EgoNode } from '@/types/explorar'

interface NodeIdentityPanelProps {
  node: EgoNode | null
  onSleep: () => void
  onDelete: () => void
}

const timeAgo = (ts: number): string => {
  if (!ts) return 'nunca'
  const diff = (Date.now() / 1000) - ts
  if (diff < 60) return `hace ${Math.floor(diff)}s`
  if (diff < 3600) return `hace ${Math.floor(diff / 60)}min`
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`
  return `hace ${Math.floor(diff / 86400)}d`
}

export function NodeIdentityPanel({ node, onSleep, onDelete }: NodeIdentityPanelProps) {
  if (!node) return null

  return (
    <div className={styles.colIzq}>
      <div className={styles.colHeader}>
        <span className={`${styles.stateDot} ${node.estado}`} />
        <h2 className={styles.nodeTitle}>{node.concepto}</h2>
      </div>
      <div className={styles.nodeBadges}>
        <span className={`${styles.badge} ${node.estado === 'activo' ? styles.badgeActivo : styles.badgeDormido}`}>
          {node.estado}
        </span>
        <span className={`${styles.badge} ${styles.badgeCat}`}>{node.categoria}</span>
      </div>
      <div className={styles.nodeMetaGrid}>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>⚖️ Peso</span>
          <span className={styles.metaValue}>{node.peso.toFixed(3)}</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>🔗 Conexiones</span>
          <span className={styles.metaValue}>{node.num_conexiones || 0}</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>⏱ Creado</span>
          <span className={styles.metaValue}>{timeAgo(node.creado_en)}</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>👁 Último acceso</span>
          <span className={styles.metaValue}>{timeAgo(node.ultimo_acceso)}</span>
        </div>
      </div>

      <div className={styles.nodeSection}>
        <h4>📝 Contenido</h4>
        <div className={styles.contentBox}>
          {node.contenido || '(vacío)'}
        </div>
      </div>

      {Object.keys(node.dimensiones).length > 0 && (
        <div className={styles.nodeSection} id="section-dimensiones">
          <h4>🎭 Dimensiones</h4>
          <div className={styles.chipList}>
            {Object.entries(node.dimensiones as Record<string, string[]>).flatMap(([eje, vals]) =>
              vals.map((v, i) => (
                <span key={`${eje}-${v}-${i}`} className={`${styles.chip} ${styles.chipDim}`} title={eje}>
                  {eje}.{v}
                </span>
              ))
            )}
          </div>
        </div>
      )}
      {node.grupos && node.grupos.length > 0 && (
        <div className={styles.nodeSection} id="section-wordnet">
          <h4>📚 WordNet</h4>
          <div className={styles.chipList}>
            {node.grupos.map((g: { nombre: string; fuente: string }, i: number) => (
              <span key={`${g.nombre}-${i}`} className={`${styles.chip} ${styles.chipWn}`} title={g.fuente}>
                {g.nombre}
              </span>
            ))}
          </div>
        </div>
      )}
      {node.sinonimos && node.sinonimos.trim() && (
        <div className={styles.nodeSection} id="section-sinonimos">
          <h4>🏷️ Sinónimos</h4>
          <div className={styles.chipList}>
            {node.sinonimos.split(',').map((s: string, i: number) => (
              <span key={`${s.trim()}-${i}`} className={styles.chip}>{s.trim()}</span>
            ))}
          </div>
        </div>
      )}
      <div className={styles.nodeActions}>
        <button className={`${styles.btnActionSm} ${styles.btnSleep}`} onClick={onSleep} title="Dormir nodo">
          😴 Dormir
        </button>
        <button className={`${styles.btnActionSm} ${styles.btnDanger}`} onClick={onDelete} title="Eliminar nodo">
          🗑️ Eliminar
        </button>
      </div>
    </div>
  )
}