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

function formatNumber(n: number): string {
  return n.toLocaleString('es-AR')
}

function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return `hace ${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `hace ${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `hace ${hours}h`
  return date.toLocaleDateString('es-AR')
}

const SaludPage = () => {
  const navigate = useNavigate()
  const [data, setData] = useState<AuditData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cleaning, setCleaning] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [lastAudit, setLastAudit] = useState<Date | null>(null)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    aislados: true,
    vacios: true,
    peso0: true,
  })

  const fetchAudit = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/salud/audit')
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      setData(await res.json())
      setLastAudit(new Date())
    } catch (e: any) {
      setError(e.message || 'Error cargando auditoría')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAudit() }, [fetchAudit])

  const limpiar = async (accion: string, count: number, label: string) => {
    const msg = accion === 'todo'
      ? `¿Eliminar TODOS los registros huérfanos? Esta acción no se puede deshacer.`
      : `¿Eliminar ${formatNumber(count)} ${label}? Esta acción no se puede deshacer.`
    if (!window.confirm(msg)) return
    setCleaning(accion)
    try {
      const res = await fetch('/api/salud/limpiar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accion }),
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const result = await res.json()
      setToast(`✓ ${result.eliminados} registros eliminados · Integridad restaurada`)
      setTimeout(() => setToast(null), 5000)
      fetchAudit()
    } catch (e: any) {
      setError(e.message || 'Error limpiando')
    } finally {
      setCleaning(null)
    }
  }

  const toggle = (key: string) => setExpanded(prev => ({ ...prev, [key]: !prev[key] }))

  // ── Separación: Integridad vs Calidad ──
  const totalIntegridad = data
    ? data.problemas.sinapsis_huerfanas + data.problemas.latentes_huerfanas
      + data.problemas.latentes_ambos_huerfanos + data.problemas.dimensiones_huerfanas
    : 0

  const totalRelaciones = data
    ? data.resumen.sinapsis_total + data.resumen.latentes_total + data.resumen.dimensiones_total
    : 0
  const integridadReferencial = totalRelaciones === 0
    ? 100
    : Math.round(((totalRelaciones - totalIntegridad) / totalRelaciones) * 100 * 10) / 10
  const integridadColor = totalIntegridad === 0 ? 'var(--green)'
    : totalIntegridad <= 5 ? 'var(--yellow)'
    : totalIntegridad <= 50 ? 'var(--orange)'
    : 'var(--red)'

  const totalNodosProblematicos = data
    ? data.problemas.nodos_aislados + data.problemas.contenido_vacio + data.problemas.peso_cero
    : 0

  // Health score: % of nodes that are NOT problematic
  const healthScore = data
    ? Math.round(((data.resumen.nodos_total - data.problemas.nodos_aislados - data.problemas.contenido_vacio - data.problemas.peso_cero) / Math.max(data.resumen.nodos_total, 1)) * 100)
    : 100

  if (loading) return <div className={styles.loading}>Cargando auditoría...</div>
  if (error) return <div className={styles.error}>Error: {error}</div>
  if (!data) return null

  const maxProblem = Math.max(
    data.problemas.sinapsis_huerfanas,
    data.problemas.latentes_huerfanas,
    data.problemas.dimensiones_huerfanas,
    data.problemas.latentes_ambos_huerfanos,
    1
  )

  const scoreColor = healthScore >= 90 ? 'var(--green)'
    : healthScore >= 70 ? 'var(--yellow)'
    : healthScore >= 50 ? 'var(--orange)'
    : 'var(--red)'

  const circumference = 2 * Math.PI * 34
  const offset = circumference - (healthScore / 100) * circumference

  const qualityColor = totalNodosProblematicos > 500 ? 'var(--red)'
    : totalNodosProblematicos > 100 ? 'var(--orange)'
    : totalNodosProblematicos > 0 ? 'var(--yellow)'
    : 'var(--green)'

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}>Mantenimiento</h1>
          {lastAudit && (
            <span className={styles.subtitle}>Última auditoría: {timeAgo(lastAudit)}</span>
          )}
        </div>
        <button className={styles.refreshBtn} onClick={fetchAudit} disabled={loading}>
          ↻ Refrescar
        </button>
      </div>

      {/* ── Sección A: Integridad referencial ── */}
      {totalIntegridad > 0 ? (
        <div className={styles.hero}>
          <div className={styles.heroScore}>
            <div className={styles.scoreRing}>
              <svg viewBox="0 0 80 80">
                <circle className={styles.scoreRingBg} cx="40" cy="40" r="34" />
                <circle
                  className={styles.scoreRingFill}
                  cx="40" cy="40" r="34"
                  stroke={integridadColor}
                  strokeDasharray={circumference}
                  strokeDashoffset={circumference - (integridadReferencial / 100) * circumference}
                />
              </svg>
              <span className={styles.scoreLabel} style={{ color: integridadColor }}>
                {totalIntegridad === 0
                  ? Number.isInteger(integridadReferencial)
                    ? `${integridadReferencial}%`
                    : `${integridadReferencial.toFixed(1)}%`
                  : `⚠ ${totalIntegridad}`}
              </span>
            </div>
            <span className={styles.scoreText}>Integridad</span>
          </div>

          <div className={styles.heroBreakdown}>
            <HeroProblemRow
              name="Sinapsis huérfanas"
              count={data.problemas.sinapsis_huerfanas}
              max={maxProblem}
              severity="red"
              onClean={() => limpiar('sinapsis_huerfanas', data.problemas.sinapsis_huerfanas, 'sinapsis huérfanas')}
              cleaning={cleaning === 'sinapsis_huerfanas'}
              info="Sinapsis que apuntan a nodos que ya no existen. Son enlaces rotos — no tienen valor y se pueden eliminar sin perder información."
            />
            <HeroProblemRow
              name="Latentes huérfanas"
              count={data.problemas.latentes_huerfanas}
              max={maxProblem}
              severity="red"
              onClean={() => limpiar('latentes_huerfanas', data.problemas.latentes_huerfanas, 'latentes huérfanas')}
              cleaning={cleaning === 'latentes_huerfanas'}
              info="Conexiones latentes que referencian nodos inexistentes. Basura de propagación — seguro de limpiar."
            />
            <HeroProblemRow
              name="Dimensiones huérfanas"
              count={data.problemas.dimensiones_huerfanas}
              max={maxProblem}
              severity="orange"
              onClean={() => limpiar('dimensiones_huerfanas', data.problemas.dimensiones_huerfanas, 'dimensiones huérfanas')}
              cleaning={cleaning === 'dimensiones_huerfanas'}
              info="Dimensiones semánticas asociadas a nodos que ya no existen. Clasificaciones huérfanas — se pueden eliminar."
            />
            <HeroProblemRow
              name="Latentes sin ambos nodos"
              count={data.problemas.latentes_ambos_huerfanos}
              max={maxProblem}
              severity="yellow"
              info="Conexiones latentes donde ni el nodo origen ni el destino existen. Más grave que una huérfana simple — indica pérdida de datos."
            />
          </div>

          <button
            className={styles.heroCleanAll}
            onClick={() => limpiar('todo', totalIntegridad, 'registros huérfanos')}
            disabled={cleaning !== null}
          >
            {cleaning === 'todo' ? 'Limpiando...' : 'Limpiar huérfanas'}
          </button>
        </div>
      ) : (
        <div className={styles.heroCollapsed}>
          <span className={styles.heroCollapsedCheck}>✓</span>
          <span className={styles.heroCollapsedText}>Integridad del grafo — sin problemas</span>
        </div>
      )}

      {/* ── Sección B: Calidad de nodos ── */}
      <div className={styles.qualitySection}>
        <div className={styles.qualityHeader}>
          <div className={styles.heroScore}>
            <div className={styles.scoreRing}>
              <svg viewBox="0 0 80 80">
                <circle className={styles.scoreRingBg} cx="40" cy="40" r="34" />
                <circle
                  className={styles.scoreRingFill}
                  cx="40" cy="40" r="34"
                  stroke={scoreColor}
                  strokeDasharray={circumference}
                  strokeDashoffset={offset}
                />
              </svg>
              <span className={styles.scoreLabel} style={{ color: scoreColor }}>
                {healthScore}%
              </span>
            </div>
            <span className={styles.scoreText}>Calidad</span>
          </div>
          <div className={styles.qualityInfo}>
            <span className={styles.qualityTitle}>Calidad de nodos</span>
            <span className={styles.qualityCount} style={{ color: qualityColor }}>
              {formatNumber(totalNodosProblematicos)} nodos con problemas
            </span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className={styles.statsGrid}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Nodos</span>
          <span className={styles.statValue}>{formatNumber(data.resumen.nodos_total)}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Sinapsis</span>
          <span className={styles.statValue}>{formatNumber(data.resumen.sinapsis_total)}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Latentes</span>
          <span className={styles.statValue}>{formatNumber(data.resumen.latentes_total)}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Dimensiones</span>
          <span className={styles.statValue}>{formatNumber(data.resumen.dimensiones_total)}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>WordNet bridge</span>
          <span className={styles.statValue}>{formatNumber(data.resumen.wordnet_bridge)}</span>
        </div>
      </div>

      {/* Nodos problemáticos — solo informativo */}
      <div className={styles.problemSection}>
        <h2 className={styles.problemSectionTitle}>Nodos problemáticos</h2>
        <div className={styles.problemList}>
          <ProblemRow
            name="Nodos aislados (sin conexiones)"
            count={data.problemas.nodos_aislados}
            accent="orange"
            info="Nodo creado pero sin conexiones a otros nodos. Puede necesitar vinculación con biorag_vincular(), no eliminación."
          />
          <ProblemRow
            name="Contenido vacío"
            count={data.problemas.contenido_vacio}
            accent="yellow"
            info="El nodo existe en la DB pero no tiene contenido guardado. No aporta información — puede eliminarse sin riesgo."
          />
          <ProblemRow
            name="Peso cero/null"
            count={data.problemas.peso_cero}
            accent="yellow"
            info="El nodo no ha sido accedido ni utilizado. Puede ser un nodo nuevo sin uso todavía, o uno que dejó de ser relevante. Requiere revisión antes de decidir."
          />
        </div>

        <div style={{ marginTop: '0.75rem' }}>
          <AccordionGroup
            title="Nodos aislados"
            items={data.detalles.nodos_aislados}
            open={!!expanded['aislados']}
            onToggle={() => toggle('aislados')}
            onNavigate={navigate}
          />
          <AccordionGroup
            title="Sin contenido"
            items={data.detalles.contenido_vacio}
            open={!!expanded['vacios']}
            onToggle={() => toggle('vacios')}
            onNavigate={navigate}
          />
          <AccordionGroup
            title="Peso cero"
            items={data.detalles.peso_cero}
            open={!!expanded['peso0']}
            onToggle={() => toggle('peso0')}
            onNavigate={navigate}
          />
        </div>
      </div>

      {toast && <div className={styles.toast}>{toast}</div>}
    </div>
  )
}

/* ── Sub-components ── */

function HeroProblemRow({
  name, count, max, severity, onClean, cleaning, info,
}: {
  name: string
  count: number
  max: number
  severity: 'red' | 'orange' | 'yellow'
  onClean?: () => void
  cleaning?: boolean
  info?: string
}) {
  const dotClass = severity === 'red' ? styles.heroDotRed
    : severity === 'orange' ? styles.heroDotOrange
    : styles.heroDotYellow

  const barColor = severity === 'red' ? 'var(--red)'
    : severity === 'orange' ? 'var(--orange)'
    : 'var(--yellow)'

  return (
    <div className={styles.heroProblemRow} data-severity={severity}>
      <div className={styles.heroProblemLeft}>
        <span className={`${styles.heroDot} ${dotClass}`} />
        <span className={styles.heroProblemName}>{name}</span>
        {info && (
          <button className={styles.infoBtn} title={info}>ℹ</button>
        )}
      </div>
      <div className={styles.heroProblemRight}>
        <span className={styles.heroProblemCount} style={{ color: count > 0 ? barColor : 'var(--text-dim)' }}>
          {formatNumber(count)}
        </span>
        <div className={styles.heroProblemBar}>
          <div
            className={styles.heroProblemBarFill}
            style={{
              width: `${max > 0 ? (count / max) * 100 : 0}%`,
              background: barColor,
            }}
          />
        </div>
        <div className={styles.heroProblemActions}>
          {onClean && count > 0 && (
            <button
              className={styles.heroCleanBtn}
              onClick={onClean}
              disabled={cleaning}
            >
              {cleaning ? '...' : '× Limpiar'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function ProblemRow({
  name, count, accent, info,
}: {
  name: string
  count: number
  accent: 'red' | 'orange' | 'yellow' | 'green'
  info?: string
}) {
  const dotClass = accent === 'red' ? styles.dotRed
    : accent === 'orange' ? styles.dotOrange
    : accent === 'yellow' ? styles.dotYellow
    : styles.dotGreen

  return (
    <div className={styles.problemRow} data-severity={accent}>
      <div className={styles.problemInfo}>
        <span className={`${styles.problemDot} ${dotClass}`} />
        <span className={styles.problemName}>{name}</span>
        {info && (
          <button className={styles.infoBtn} title={info}>ℹ</button>
        )}
      </div>
      <div className={styles.problemActions}>
        <span className={styles.problemCount}>{formatNumber(count)}</span>
      </div>
    </div>
  )
}

function AccordionGroup({
  title, items, open, onToggle, onNavigate,
}: {
  title: string
  items: string[]
  open: boolean
  onToggle: () => void
  onNavigate: (path: string) => void
}) {
  if (items.length === 0) return null

  return (
    <div className={styles.detailGroup}>
      <button className={styles.detailToggle} onClick={onToggle}>
        <div className={styles.detailToggleLeft}>
          <span className={`${styles.detailChevron} ${open ? styles.detailChevronOpen : ''}`}>
            ▶
          </span>
          <span className={styles.detailToggleLabel}>{title}</span>
          <span className={styles.detailToggleHint}>
            {open ? '— click para colapsar' : '— click para ver'}
          </span>
        </div>
        <span className={styles.detailCount}>{items.length}</span>
      </button>
      {open && (
        <div className={styles.detailBody}>
          <div className={styles.nodeList}>
            {items.map(n => (
              <span
                key={n}
                className={styles.nodeTag}
                onClick={() => onNavigate(`/explorar/${encodeURIComponent(n)}`)}
                title={`Inspeccionar ${n}`}
              >
                {n.length > 35 ? n.substring(0, 32) + '...' : n}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default SaludPage
