import { useEffect, useState, useCallback } from "react";
import { useApi } from "../../hooks/useApi";
import { getCortezaEstado, getCortezaActividad, getBuscadasFallidas, getNodosEnRiesgo } from "../../services/api";
import type { CortezaEstado, CortezaActividad, EnergyPoint, BuscadaFallida, NodoEnRiesgo } from "../../types";
import styles from "./CortezaPage.module.css";
import StatCard from "../../components/StatCard/StatCard";
import BarChart from "../../components/BarChart/BarChart";
import StackedBarChart from "../../components/StackedBarChart/StackedBarChart";
import EnergyLineChart from "../../components/EnergyLineChart/EnergyLineChart";
import DetallePunto from "../../components/DetallePunto/DetallePunto";
import RepairCard, { type RepairItem } from "../../components/RepairCard/RepairCard";

const CortezaPage = () => {
  const [estado, setEstado] = useState<CortezaEstado | null>(null);
  const [actividad, setActividad] = useState<CortezaActividad | null>(null);
  const [puntoSeleccionado, setPuntoSeleccionado] =
    useState<EnergyPoint | null>(null);
  const [buscadasFallidas, setBuscadasFallidas] = useState<RepairItem[]>([]);
  const [nodosEnRiesgo, setNodosEnRiesgo] = useState<RepairItem[]>([]);
  const [fallidasTotal, setFallidasTotal] = useState(0);
  const [riesgoTotal, setRiesgoTotal] = useState(0);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
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

  const fetchRepairData = useCallback(async () => {
    try {
      const [fallidas, riesgo] = await Promise.all([
        getBuscadasFallidas(10),
        getNodosEnRiesgo(10),
      ]);
      setFallidasTotal(fallidas.total);
      setRiesgoTotal(riesgo.total);
      setBuscadasFallidas(
        fallidas.items.map((f: BuscadaFallida) => ({
          label: f.query,
          meta: `${f.freq}x \u00b7 score ${f.top_score} \u00b7 ${f.ultima_hace}`,
          raw: f,
        }))
      );
      setNodosEnRiesgo(
        riesgo.items.map((r: NodoEnRiesgo) => ({
          label: r.concepto,
          meta: `peso ${r.peso} \u00b7 ${r.dias_idle}d \u00b7 ${r.categoria}`,
          raw: r,
        }))
      );
    } catch {
      // endpoints might not exist yet
    }
  }, []);

  useEffect(() => {
    fetchRepairData();
  }, [fetchRepairData]);

  const handlePointClick = (punto: EnergyPoint) => {
    setPuntoSeleccionado(punto);
  };

  const handleRefresh = () => {
    refetchEstado();
    refetchActividad();
    fetchRepairData();
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

      <div className={styles.repairConsole}>
        <RepairCard
          icon={"🔍"}
          title="Búsquedas que fallaron"
          total={fallidasTotal}
          count={buscadasFallidas.length}
          items={buscadasFallidas}
          actionLabel="Crear nodo"
          infoTooltip="Búsquedas que no encontraron suficientes resultados. Indican recuerdos que deberían existir pero no están guardados. Si no creas estos nodos, cada vez que busques algo relacionado no encontrarás nada y tendrás que empezar de cero. Usa 'Crear nodo' para agregar un recuerdo básico y que futuras búsquedas lo encuentren."
          loadingKey={loadingAction}
          onAction={async (item) => {
            setLoadingAction(item.label);
            try {
              await fetch("http://localhost:8001/api/nodo", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  concepto: item.label,
                  contenido: `Nodo creado automáticamente por búsqueda fallida: ${item.label}`,
                  syn: item.label,
                }),
              });
              fetchRepairData();
            } catch {
              // ignore
            } finally {
              setLoadingAction(null);
            }
          }}
        />
        <RepairCard
          icon={"⚠️"}
          title="Nodos importantes en riesgo"
          total={riesgoTotal}
          count={nodosEnRiesgo.length}
          items={nodosEnRiesgo}
          actionLabel="Acceder ahora"
          infoTooltip={"Nodos con peso sináptico alto (>0.7) pero sin ser accedidos en más de 3 días. Riesgo de quedar dormidos por falta de uso.\n\nNOTA: Recuerdos importantes que llevan varios días sin usarse. Si no se acceden pronto, serán difíciles de encontrar después. Usa 'Acceder ahora' para mantenerlos activos.\n\nCuando un nodo duerme:\n- No aparece en búsquedas normales\n- Necesita deep=True o ráfaga específica para encontrarlo\n- Se pierde \"conectividad\" en el grafo\n- Cuesta más energía reactivarlo después"}
          loadingKey={loadingAction}
          onAction={async (item) => {
            setLoadingAction(item.label);
            try {
              await fetch(`http://localhost:8001/api/buscar?q=${encodeURIComponent(item.label)}`);
              fetchRepairData();
            } catch {
              // ignore
            } finally {
              setLoadingAction(null);
            }
          }}
        />
      </div>

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
