import { useEffect, useState } from 'react'
import { useApi } from '../../hooks/useApi'
import { getCortezaEstado, getCortezaActividad } from '../../services/api'
import type { CortezaEstado, CortezaActividad } from '../../types'
import styles from './CortezaPage.module.css'
import StatCard from '../../components/StatCard/StatCard'
import BarChart from '../../components/BarChart/BarChart'
import EnergyLineChart from '../../components/EnergyLineChart/EnergyLineChart'

const CortezaPage = () => {
  const [estado, setEstado] = useState<CortezaEstado | null>(null)
  const [actividad, setActividad] = useState<CortezaActividad | null>(null)
  const { data: estadoData, loading: estadoLoading, error: estadoError, refetch: refetchEstado } = useApi(() => getCortezaEstado())
  const { data: actividadData, loading: actividadLoading, error: actividadError, refetch: refetchActividad } = useApi(() => getCortezaActividad(7))

  useEffect(() => {
    if (estadoData) setEstado(estadoData)
  }, [estadoData])

  useEffect(() => {
    if (actividadData) setActividad(actividadData)
  }, [actividadData])

  const handleRefresh = () => {
    refetchEstado()
    refetchActividad()
  }

  if (estadoLoading || actividadLoading) {
    return <div className={styles.loading}>Cargando corteza...</div>
  }

  if (estadoError || actividadError || !estado) {
    return <div className={styles.error}>Error cargando datos: {estadoError || actividadError || 'Datos incompletos'}</div>
  }

  const energiaPct = estado.energia_pct ?? Math.min(100, (estado.energia / Math.max(estado.energia_max, 1)) * 100)

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>⚡ Estado de la Corteza</h1>
        <button className={styles.refreshBtn} onClick={handleRefresh} disabled={estadoLoading || actividadLoading}>
          {estadoLoading || actividadLoading ? '⟳ Actualizando...' : '🔄 Actualizar'}
        </button>
      </header>

      <section className={styles.statsGrid} aria-label="Estadísticas principales">
        <StatCard label="Fuerza de conexiones" value={estado.energia.toFixed(2)} accent progress={energiaPct} progressLabel={`${energiaPct.toFixed(1)}%`} description="Qué tan fácil le es al cerebro conectar recuerdos" />
        <StatCard label="Recuerdos activos" value={estado.activos} description="Recuerdos que el cerebro está usando ahora" />
        <StatCard label="Recuerdos dormidos" value={estado.dormidos} description="Recuerdos que se apagaron por no usarse" />
        <StatCard label="Conexiones directas" value={estado.directas.toLocaleString()} description="Recuerdos que están vinculados entre sí" />
        <StatCard label="Conexiones sugeridas" value={estado.latentes.toLocaleString()} description="Recuerdos que el cerebro intuya que podrían estar relacionados" />
        <StatCard label="Última revisión" value={estado.ultimo_sueno} description="Cuándo el cerebro se organizó por última vez" />
        <StatCard label="Velocidad" value={`${estado.latencia_ms} ms`} description="Cuánto tarda el cerebro en encontrar un recuerdo" />
      </section>

      <div className={styles.twoCol}>
        <section className={styles.panel} aria-label="Distribución por categoría">
          <h2 className={styles.panelTitle}>Distribución por Categoría</h2>
          <BarChart
            title="Distribución por Categoría"
            data={estado.categorias
              .sort((a, b) => b.count - a.count)
              .map(c => ({
                label: c.nombre,
                value: c.count,
                color: getCategoryColor(c.nombre),
              }))}
            showValue
          />
        </section>

        <section className={styles.panel} aria-label="Dimensiones más activas">
          <h2 className={styles.panelTitle}>Dimensiones Más Activas</h2>
          <BarChart
            title="Dimensiones Más Activas"
            data={estado.dimensiones_top
              .sort((a, b) => b.count - a.count)
              .map(d => ({
                label: `${d.eje}.${d.valor}`,
                value: d.count,
                color: 'var(--accent-color)',
              }))}
            showValue
          />
        </section>
      </div>

      <section className={styles.panel} aria-label="Métricas de ciclos (cada vez que el cerebro se consolida) (7 días)">
        <h2 className={styles.panelTitle}>Métricas de ciclos (cada vez que el cerebro se consolida) (7 días)</h2>
        <EnergyLineChart
          title="Métricas de ciclos (cada vez que el cerebro se consolida)"
          data={actividad?.energia_historial ?? []}
        />
      </section>
    </div>
  )
}

function getCategoryColor(nombre: string): string {
  const colors: Record<string, string> = {
    Principle: '#f97316',
    Lesson: '#10b981',
    Architecture: '#3b82f6',
    Project: '#06b6d4',
    System: '#a855f7',
    Protocol: '#eab308',
    Profile: '#00ffff',
    Cognition: '#a855f7',
    Relation: '#f43f5e',
    Personal: '#14b8a6',
    General: '#94a3b8',
  }
  return colors[nombre] || '#6b7280'
}

export default CortezaPage