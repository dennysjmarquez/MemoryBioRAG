import { useEffect, useState } from "react";
import { useApi } from "../../hooks/useApi";
import { getCortezaEstado, getCortezaActividad } from "../../services/api";
import type { CortezaEstado, CortezaActividad, EnergyPoint } from "../../types";
import styles from "./CortezaPage.module.css";
import StatCard from "../../components/StatCard/StatCard";
import BarChart from "../../components/BarChart/BarChart";
import StackedBarChart from "../../components/StackedBarChart/StackedBarChart";
import EnergyLineChart from "../../components/EnergyLineChart/EnergyLineChart";
import DetallePunto from "../../components/DetallePunto/DetallePunto";

const CortezaPage = () => {
  const [estado, setEstado] = useState<CortezaEstado | null>(null);
  const [actividad, setActividad] = useState<CortezaActividad | null>(null);
  const [puntoSeleccionado, setPuntoSeleccionado] =
    useState<EnergyPoint | null>(null);
  const {
    data: estadoData,
    loading: estadoLoading,
    error: estadoError,
    refetch: refetchEstado,
  } = useApi(() => getCortezaEstado());
  const {
    data: actividadData,
    loading: actividadLoading,
    error: actividadError,
    refetch: refetchActividad,
  } = useApi(() => getCortezaActividad(7));

  useEffect(() => {
    if (estadoData) setEstado(estadoData);
  }, [estadoData]);

  useEffect(() => {
    if (actividadData) setActividad(actividadData);
  }, [actividadData]);

  const handlePointClick = (punto: EnergyPoint) => {
    setPuntoSeleccionado(punto);
  };

  const handleRefresh = () => {
    refetchEstado();
    refetchActividad();
  };

  if (estadoLoading || actividadLoading) {
    return <div className={styles.loading}>Cargando corteza...</div>;
  }

  if (estadoError || actividadError || !estado) {
    return (
      <div className={styles.error}>
        Error cargando datos:{" "}
        {estadoError || actividadError || "Datos incompletos"}
      </div>
    );
  }

  const energiaPct =
    estado.energia_pct ??
    Math.min(100, (estado.energia / Math.max(estado.energia_max, 1)) * 100);

  return (
    <>
      <header className={styles.header}>
        <h1 className={styles.title}>⚡ Estado de la Corteza</h1>
        <button
          className={styles.refreshBtn}
          onClick={handleRefresh}
          disabled={estadoLoading || actividadLoading}
        >
          {estadoLoading || actividadLoading
            ? "⟳ Actualizando..."
            : "🔄 Actualizar"}
        </button>
      </header>

      <section
        className={styles.statsGrid}
        aria-label="Estadísticas principales"
      >
        <StatCard
          icon="⚡"
          label="Energía Sináptica"
          value={estado.energia.toFixed(2)}
          maxValue={500}
          color="blue"
          progress={energiaPct}
          progressLabel={`${energiaPct.toFixed(1)}% de fuerza`}
        />
        <StatCard
          icon="🧠"
          label="Activos"
          value={estado.activos}
          color="green"
          description="Recuerdos vivos"
        />
        <StatCard
          icon="😴"
          label="Dormidos"
          value={estado.dormidos}
          color="yellow"
          description="En reposo"
        />
        <StatCard
          icon="🔗"
          label="Sinapsis Directas"
          value={estado.directas.toLocaleString()}
          color="purple"
          description="Vinculados entre sí"
        />
        <StatCard
          icon="💫"
          label="Sinapsis Latentes"
          value={estado.latentes.toLocaleString()}
          color="cyan"
          description="Potencialmente relacionados"
        />
        <StatCard
          icon="⏱"
          label="Último Sueño"
          value={estado.ultimo_sueno}
          color="blue"
          description="Última organización"
        />
        <StatCard
          icon="📊"
          label="Latencia Búsqueda"
          value={`${estado.latencia_ms}ms`}
          color="green"
          description="Velocidad de recuperación"
        />
      </section>

      <div className={styles.twoCol}>
        <section
          className={styles.panel}
          aria-label="Distribución por categoría"
        >
          <h2 className={styles.panelTitle}>Distribución por Categoría</h2>
          <StackedBarChart
            title="Distribución por Categoría"
            data={estado.categorias.map((c) => ({
              label: c.nombre,
              activos: c.activos,
              dormidos: c.dormidos,
              total: c.total,
              color: getCategoryColor(c.nombre),
            }))}
          />
        </section>

        <section className={styles.panel} aria-label="Dimensiones más activas">
          <h2 className={styles.panelTitle}>Dimensiones Más Activas</h2>
          <BarChart
            title="Dimensiones Más Activas"
            data={estado.dimensiones_top
              .sort((a, b) => b.count - a.count)
              .map((d) => ({
                label: `${d.eje}.${d.valor}`,
                value: d.count,
                color: "var(--accent-color)",
                eje: d.eje,
                valor: d.valor,
              }))}
            showValue
            showColumns
          />
        </section>
      </div>

      <div className={styles.twoCol}>
        <section className={styles.panel} aria-label="Actividad del cerebro">
          <h2 className={styles.panelTitle}>Actividad del cerebro (7 días)</h2>
          <EnergyLineChart
            data={actividad?.energia_historial ?? []}
            ciclos={actividad?.ciclos ?? []}
            onPointClick={handlePointClick}
            selectedPoint={puntoSeleccionado}
          />
        </section>
      </div>
      <div className={styles.twoCol}>
        <section
          className={styles.detailPanel}
          aria-label="Detalle del punto seleccionado"
        >
          <DetallePunto
            punto={puntoSeleccionado}
            onClose={() => setPuntoSeleccionado(null)}
          />
        </section>
      </div>
    </>
  );
};

function getCategoryColor(nombre: string): string {
  const colors: Record<string, string> = {
    Principle: "#f97316",
    Lesson: "#10b981",
    Architecture: "#3b82f6",
    Project: "#06b6d4",
    System: "#a855f7",
    Protocol: "#eab308",
    Profile: "#00ffff",
    Cognition: "#a855f7",
    Relation: "#f43f5e",
    Personal: "#14b8a6",
    General: "#94a3b8",
  };
  return colors[nombre] || "#6b7280";
}

export default CortezaPage;
