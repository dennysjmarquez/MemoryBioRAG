import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import styles from './SaludPage.module.css'

interface AuditData {
  resumen: {
    nodos_total: number
    sinapsis_total: number
    latentes_total: number
    dimensiones_total: number
    wordnet_bridge: number
  }
  problemas: {
    sinapsis_huerfanas: number
    latentes_huerfanas: number
    latentes_ambos_huerfanos: number
    dimensiones_huerfanas: number
    nodos_aislados: number
    contenido_vacio: number
    peso_cero: number
  }
  detalles: {
    nodos_aislados: string[]
    contenido_vacio: string[]
    peso_cero: string[]
  }
}

const SaludPage = () => {
  const navigate = useNavigate()
  const [data, setData] = useState<AuditData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cleaning, setCleaning] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const fetchAudit = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/salud/audit')
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      setData(await res.json())
    } catch (e: any) {
      setError(e.message || 'Error cargando auditoría')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAudit() }, [fetchAudit])

  const limpiar = async (accion: string) => {
    setCleaning(accion)
    try {
      const res = await fetch('/api/salud/limpiar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accion }),
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const result = await res.json()
      setToast(`${result.eliminados} registros eliminados`)
      setTimeout(() => setToast(null), 3000)
      fetchAudit()
    } catch (e: any) {
      setError(e.message || 'Error limpiando')
    } finally {
      setCleaning(null)
    }
  }

  const totalProblemas = data ? Object.values(data.problemas).reduce((a, b) => a + b, 0) : 0

  if (loading) return <div className={styles.loading}>Cargando auditoría...</div>
  if (error) return <div className={styles.error}>Error: {error}</div>
  if (!data) return null

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Mantenimiento</h1>
        <button className={styles.refreshBtn} onClick={fetchAudit} disabled={loading}>
          ↻ Refrescar
        </button>
      </div>

      {/* Resumen */}
      <div className={styles.statsGrid}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Nodos</span>
          <span className={styles.statValue}>{data.resumen.nodos_total}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Sinapsis</span>
          <span className={styles.statValue}>{data.resumen.sinapsis_total}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Latentes</span>
          <span className={styles.statValue}>{data.resumen.latentes_total}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Dimensiones</span>
          <span className={styles.statValue}>{data.resumen.dimensiones_total}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>WordNet bridge</span>
          <span className={styles.statValue}>{data.resumen.wordnet_bridge}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Problemas</span>
          <span className={styles.statValue} style={{ color: totalProblemas > 0 ? 'var(--red)' : 'var(--green)' }}>
            {totalProblemas}
          </span>
        </div>
      </div>

      {/* Integridad */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Integridad del grafo</h2>
          {totalProblemas > 0 && (
            <button
              className={styles.cleanBtnAll}
              onClick={() => limpiar('todo')}
              disabled={cleaning !== null}
            >
              {cleaning === 'todo' ? 'Limpiando...' : 'Limpiar todo'}
            </button>
          )}
        </div>
        <div className={styles.problemList}>
          <ProblemRow
            name="Sinapsis huérfanas"
            count={data.problemas.sinapsis_huerfanas}
            accent="red"
            onClean={() => limpiar('sinapsis_huerfanas')}
            cleaning={cleaning === 'sinapsis_huerfanas'}
          />
          <ProblemRow
            name="Latentes huérfanas"
            count={data.problemas.latentes_huerfanas}
            accent="red"
            onClean={() => limpiar('latentes_huerfanas')}
            cleaning={cleaning === 'latentes_huerfanas'}
          />
          <ProblemRow
            name="Dimensiones huérfanas"
            count={data.problemas.dimensiones_huerfanas}
            accent="orange"
            onClean={() => limpiar('dimensiones_huerfanas')}
            cleaning={cleaning === 'dimensiones_huerfanas'}
          />
          <ProblemRow
            name="Latentes sin ambos nodos"
            count={data.problemas.latentes_ambos_huerfanos}
            accent="yellow"
          />
        </div>
      </div>

      {/* Nodos problemáticos */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Nodos problemáticos</h2>
        </div>
        <div className={styles.problemList}>
          <ProblemRow name="Nodos aislados (sin conexiones)" count={data.problemas.nodos_aislados} accent="orange" />
          <ProblemRow name="Contenido vacío" count={data.problemas.contenido_vacio} accent="yellow" />
          <ProblemRow name="Peso cero/null" count={data.problemas.peso_cero} accent="yellow" />
        </div>

        {data.detalles.nodos_aislados.length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <div style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: '0.5rem' }}>
              Nodos aislados:
            </div>
            <div className={styles.nodeList}>
              {data.detalles.nodos_aislados.map(n => (
                <span
                  key={n}
                  className={styles.nodeTag}
                  onClick={() => navigate(`/explorar/${encodeURIComponent(n)}`)}
                  title={`Inspeccionar ${n}`}
                >
                  {n.length > 35 ? n.substring(0, 32) + '...' : n}
                </span>
              ))}
            </div>
          </div>
        )}

        {data.detalles.contenido_vacio.length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <div style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: '0.5rem' }}>
              Sin contenido:
            </div>
            <div className={styles.nodeList}>
              {data.detalles.contenido_vacio.map(n => (
                <span
                  key={n}
                  className={styles.nodeTag}
                  onClick={() => navigate(`/explorar/${encodeURIComponent(n)}`)}
                >
                  {n}
                </span>
              ))}
            </div>
          </div>
        )}

        {data.detalles.peso_cero.length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <div style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: '0.5rem' }}>
              Peso cero:
            </div>
            <div className={styles.nodeList}>
              {data.detalles.peso_cero.map(n => (
                <span
                  key={n}
                  className={styles.nodeTag}
                  onClick={() => navigate(`/explorar/${encodeURIComponent(n)}`)}
                >
                  {n}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {toast && <div className={styles.toast}>{toast}</div>}
    </div>
  )
}

function ProblemRow({
  name,
  count,
  accent,
  onClean,
  cleaning,
}: {
  name: string
  count: number
  accent: 'red' | 'orange' | 'yellow' | 'green'
  onClean?: () => void
  cleaning?: boolean
}) {
  const dotClass = accent === 'red' ? styles.dotRed
    : accent === 'orange' ? styles.dotOrange
    : accent === 'yellow' ? styles.dotYellow
    : styles.dotGreen

  return (
    <div className={styles.problemRow}>
      <div className={styles.problemInfo}>
        <span className={`${styles.problemDot} ${dotClass}`} />
        <span className={styles.problemName}>{name}</span>
      </div>
      <div className={styles.problemActions}>
        <span className={styles.problemCount}>{count}</span>
        {onClean && count > 0 && (
          <button
            className={styles.cleanBtn}
            onClick={onClean}
            disabled={cleaning}
          >
            {cleaning ? '...' : '× Limpiar'}
          </button>
        )}
      </div>
    </div>
  )
}

export default SaludPage
