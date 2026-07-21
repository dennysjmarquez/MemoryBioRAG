import { useEffect, useState, useCallback } from "react";
import { useApi } from "../../hooks/useApi";
import { getCortezaEstado, getCortezaActividad, getBuscadasFallidas, getNodosEnRiesgo, limpiarLogBusquedas, tocarNodo } from "../../services/api";
import type { CortezaEstado, CortezaActividad, EnergyPoint, BuscadaFallida, NodoEnRiesgo } from "../../types";
import styles from "./CortezaPage.module.css";
import StatCard from "../../components/StatCard/StatCard";
import BarChart from "../../components/BarChart/BarChart";
import StackedBarChart from "../../components/StackedBarChart/StackedBarChart";
import EnergyLineChart from "../../components/EnergyLineChart/EnergyLineChart";
import DetallePunto from "../../components/DetallePunto/DetallePunto";
import RepairCard, { type RepairItem } from "../../components/RepairCard/RepairCard";
import FailedSearchAccordion from "../../components/FailedSearchAccordion/FailedSearchAccordion";
import ActionFeedbackModal from "../../components/ActionFeedbackModal/ActionFeedbackModal";

const CortezaPage = () => {
  const [estado, setEstado] = useState<CortezaEstado | null>(null);
  const [actividad, setActividad] = useState<CortezaActividad | null>(null);
  const [puntoSeleccionado, setPuntoSeleccionado] =
    useState<EnergyPoint | null>(null);
  const [buscadasFallidas, setBuscadasFallidas] = useState<BuscadaFallida[]>([]);
  const [nodosEnRiesgo, setNodosEnRiesgo] = useState<RepairItem[]>([]);
  const [riesgoTotal, setRiesgoTotal] = useState(0);
  const [clearing, setClearing] = useState(false);
  const [feedback, setFeedback] = useState<{
    open: boolean
    state: 'loading' | 'success' | 'error'
    title: string
    target: string
    message: string
    detail?: string
  }>({ open: false, state: 'loading', title: '', target: '', message: '' });
  const closeFeedback = () => setFeedback(f => ({ ...f, open: false }));

  async function runWithFeedback(
    opts: { title: string; target: string; loadingMsg: string },
    action: () => Promise<{ ok: boolean; message: string; detail?: string }>
  ) {
    setFeedback({ open: true, state: 'loading', title: opts.title, target: opts.target, message: opts.loadingMsg });
    let result: { ok: boolean; message: string; detail?: string };
    try {
      result = await action();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      result = { ok: false, message: 'Error de red', detail: msg };
    }
    setFeedback({
      open: true,
      state: result.ok ? 'success' : 'error',
      title: opts.title,
      target: opts.target,
      message: result.message,
      detail: result.detail,
    });
    if (result.ok) fetchRepairData();
  }
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
        getBuscadasFallidas(),
        getNodosEnRiesgo(25),
      ]);
        setRiesgoTotal(riesgo.total);
      setBuscadasFallidas(fallidas.items);
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
        <div className={styles.repairCard}>
          <div className={styles.repairCardHeader}>
            <span className={styles.repairCardIcon}>🔍</span>
            <span className={styles.repairCardTitle}>Búsquedas que fallaron</span>
            <span className={styles.infoIcon} title="Búsquedas fallidas: menos de 3 resultados O top_score < 0.55 (mucho ruido sin match útil). Incluye vacías y las que devolvieron basura irrelevante. Indican recuerdos que deberían existir pero no están. Usa 'Crear nodo' para que futuras búsquedas los encuentren.">ℹ</span>
            <span className={`${styles.repairCardBadge} ${styles.repairCardBadgeWarn}`}>
              {buscadasFallidas.length}
            </span>
          </div>
          <FailedSearchAccordion
            items={buscadasFallidas}
            loadingKey={null}
            onCreateNode={(query) =>
              runWithFeedback(
                { title: 'Crear nodo', target: query, loadingMsg: 'Creando nodo en BioRAG...' },
                async () => {
                  const res = await fetch("http://localhost:8001/api/nodo", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      concepto: query,
                      contenido: `Nodo creado automáticamente por búsqueda fallida: ${query}`,
                      syn: query,
                    }),
                  });
                  if (!res.ok) {
                    return { ok: false, message: 'No se pudo crear el nodo', detail: `HTTP ${res.status}` };
                  }
                  return { ok: true, message: 'Nodo creado correctamente', detail: query };
                }
              )
            }
            onClear={async () => {
              if (clearing) return;
              setClearing(true);
              try {
                await limpiarLogBusquedas(7);
                fetchRepairData();
              } catch {
                // ignore
              } finally {
                setClearing(false);
              }
            }}
            clearing={clearing}
          />
        </div>
        <RepairCard
          icon={"⚠️"}
          title="Nodos importantes en riesgo"
          total={riesgoTotal}
          count={nodosEnRiesgo.length}
          items={nodosEnRiesgo}
          actionLabel="Acceder ahora"
          infoTooltip={"Nodos con peso sináptico alto (>0.7) pero sin ser accedidos en más de 3 días. Riesgo de quedar dormidos por falta de uso.\n\nNOTA: Recuerdos importantes que llevan varios días sin usarse. Si no se acceden pronto, serán difíciles de encontrar después. Usa 'Acceder ahora' para mantenerlos activos.\n\nCuando un nodo duerme:\n- No aparece en búsquedas normales\n- Necesita deep=True o ráfaga específica para encontrarlo\n- Se pierde \"conectividad\" en el grafo\n- Cuesta más energía reactivarlo después"}
          loadingKey={null}
          onAction={(item) =>
            runWithFeedback(
              { title: 'Acceder ahora', target: item.label, loadingMsg: 'Marcando nodo como accedido...' },
              async () => {
                const data = await tocarNodo(item.label);
                if (!data.ok) {
                  return {
                    ok: false,
                    message: 'No se encontró el nodo',
                    detail: data.actualizados === 0
                      ? `No existe "${item.label}" en BioRAG`
                      : `actualizados=${data.actualizados}`,
                  };
                }
                return {
                  ok: true,
                  message: 'Nodo marcado como accedido',
                  detail: 'Último acceso actualizado • ya no aparecerá en riesgo',
                };
              }
            )
          }
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

      <ActionFeedbackModal
        open={feedback.open}
        state={feedback.state}
        title={feedback.title}
        target={feedback.target}
        message={feedback.message}
        detail={feedback.detail}
        onClose={closeFeedback}
      />
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
