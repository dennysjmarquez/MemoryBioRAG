import { EnergyPoint } from "../../types"
import styles from "./DetallePunto.module.css"

interface DetallePuntoProps {
  punto: EnergyPoint | null
  onClose: () => void
}

const DetallePunto = ({ punto, onClose }: DetallePuntoProps) => {
  if (!punto) return null

  return (
    <div className={styles.panel} role="region" aria-label="Detalle de medición">
      <header className={styles.header}>
        <h3 className={styles.title}>
          📅 {new Date(punto.timestamp * 1000).toLocaleDateString("es-ES", {
            weekday: "long",
            day: "numeric",
            month: "long",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </h3>
        <button className={styles.closeBtn} onClick={onClose} aria-label="Cerrar detalle">
          ✕
        </button>
      </header>

      <div className={styles.content}>
        <div className={styles.grid}>
          <StatCard
            icon="⚡"
            label="Fuerza de conexiones"
            value={punto.energia.toFixed(2)}
            accent
          />
          <StatCard
            icon="🧠"
            label="Recuerdos activos"
            value={punto.activos}
          />
          <StatCard
            icon="🌙"
            label="Recuerdos dormidos"
            value={punto.dormidos}
          />
          <StatCard
            icon="📊"
            label="Total de recuerdos"
            value={punto.total_nodos}
          />
          <StatCard
            icon="📂"
            label="Categoría dominante"
            value={punto.categoria_dominante || "N/A"}
            accent
          />
          <StatCard
            icon="⏱️"
            label="Velocidad de búsqueda"
            value={`${punto.latencia_ms} ms`}
          />
        </div>

        {punto.conceptos && punto.conceptos.length > 0 && (
          <section className={styles.conceptos}>
            <h4 className={styles.conceptosTitle}>🧠 Conceptos consolidados en este momento</h4>
            <ul className={styles.conceptosList}>
              {punto.conceptos.map((c: { concepto: string; contenido: string }, i: number) => (
                <li key={i} className={styles.conceptoItem}>
                  <code className={styles.conceptoNombre}>{c.concepto}</code>
                  <p className={styles.conceptoContenido}>{c.contenido}</p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  )
}

const StatCard = ({
  icon,
  label,
  value,
  accent = false,
}: {
  icon: string
  label: string
  value: string | number
  accent?: boolean
}) => (
  <div className={`${styles.stat} ${accent ? styles.accent : ""}`}>
    <span className={styles.statIcon}>{icon}</span>
    <div>
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>{value}</span>
    </div>
  </div>
)

export default DetallePunto