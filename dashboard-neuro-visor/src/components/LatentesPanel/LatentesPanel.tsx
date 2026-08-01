import styles from './LatentesPanel.module.css'

interface LatentesPanelProps {
  latentes: {
    destino_concepto: string
    peso: number
    saltos: number
    destino_categoria: string
    destino_preview: string
  }[]
  onNavigate: (concepto: string) => void
  totalReal: number
  onLoadMore: () => void
  hasMore: boolean
}

export function LatentesPanel({ latentes, onNavigate, totalReal, onLoadMore, hasMore }: LatentesPanelProps) {
  return (
    <div className={styles.colDer}>
      <div className={styles.colHeader}>
        <h3>🌀 Latentes (<span id="lat-total">{totalReal}</span>)</h3>
        {latentes.length < totalReal && (
          <span style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
            Mostrando {latentes.length} de {totalReal}
          </span>
        )}
      </div>
      <div className={styles.latentesList}>
        {latentes.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '20px', fontSize: '12px' }}>
            Sin sinapsis latentes
          </div>
        ) : (
          latentes.map((l, i) => (
            <div key={`${l.destino_concepto}-${i}`} className={styles.latCard}>
              <div
                className={styles.latCardName}
                onClick={() => onNavigate(l.destino_concepto)}
              >
                {l.destino_concepto}
              </div>
              <div className={styles.latCardMeta}>
                <span>p={l.peso.toFixed(2)}</span>
                <span>{l.saltos} saltos</span>
                <span>{l.destino_categoria}</span>
              </div>
            </div>
          ))
        )}
        {hasMore && (
          <button
            onClick={onLoadMore}
            style={{
              width: '100%',
              padding: '10px',
              marginTop: '8px',
              background: 'var(--bg-secondary)',
              color: 'var(--text)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            Cargar más ({latentes.length} de {totalReal})
          </button>
        )}
      </div>
    </div>
  )
}