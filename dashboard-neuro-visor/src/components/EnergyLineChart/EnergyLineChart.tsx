import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import styles from "./EnergyLineChart.module.css";
import type { CicloActividad, EnergyPoint } from "../../types";

interface EnergyLineChartProps {
  data: EnergyPoint[];
  ciclos?: CicloActividad[];
  height?: number;
  onPointClick?: (punto: EnergyPoint) => void;
}

const formatDate = (timestamp: number) => {
  const date = new Date(timestamp * 1000);
  return date.toLocaleDateString("es-ES", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const getHealthStatus = (activos: number, total: number) => {
  if (total === 0) return { label: "Sin datos", emoji: "⚪", color: "#6b7280" };
  const pct = (activos / total) * 100;
  if (pct > 70) return { label: "Activo", emoji: "🟢", color: "#10b981" };
  if (pct > 30) return { label: "Normal", emoji: "🟡", color: "#eab308" };
  return { label: "En reposo", emoji: "🔴", color: "#ef4444" };
};

const CustomTooltip = ({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: any; value: number }>;
}) => {
  if (!active || !payload || !payload[0]) return null;

  const point = payload[0].payload as EnergyPoint;
  const health = getHealthStatus(point.activos, point.total_nodos);

  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipHeader}>
        <span className={styles.tooltipDate}>{formatDate(point.timestamp)}</span>
        <span className={styles.tooltipHealth} style={{ color: health.color }}>
          {health.emoji} {health.label}
        </span>
      </div>

      <div className={styles.tooltipDivider} />

      <div className={styles.tooltipGrid}>
        <div className={styles.tooltipStat}>
          <span className={styles.tooltipStatValue}>{point.energia.toFixed(1)}</span>
          <span className={styles.tooltipStatLabel}>energía</span>
        </div>
        <div className={styles.tooltipStat}>
          <span className={styles.tooltipStatValue}>{point.activos}</span>
          <span className={styles.tooltipStatLabel}>activos</span>
        </div>
        <div className={styles.tooltipStat}>
          <span className={styles.tooltipStatValue}>{point.dormidos}</span>
          <span className={styles.tooltipStatLabel}>dormidos</span>
        </div>
        <div className={styles.tooltipStat}>
          <span className={styles.tooltipStatValue}>{point.total_nodos}</span>
          <span className={styles.tooltipStatLabel}>total</span>
        </div>
      </div>

      {point.categoria_dominante && (
        <div className={styles.tooltipCategory}>
          Más fuerte: <strong>{point.categoria_dominante}</strong>
        </div>
      )}

      {point.conceptos && point.conceptos.length > 0 && (
        <>
          <div className={styles.tooltipDivider} />
          <div className={styles.tooltipConceptos}>
            <span className={styles.tooltipConceptosTitle}>
              {point.conceptos.length} {point.conceptos.length === 1 ? 'recuerdo tocado' : 'recuerdos tocados'}
            </span>
          </div>
        </>
      )}

      {(!point.conceptos || point.conceptos.length === 0) && (
        <div className={styles.tooltipEmpty}>
          Sin actividad nueva en este momento
        </div>
      )}
    </div>
  );
};

const ChartLegend = () => (
  <div className={styles.legend}>
    <div className={styles.legendItem}>
      <span className={styles.legendDot} style={{ background: "#10b981" }} />
      <span>Activo (más de 70% de recuerdos vivos)</span>
    </div>
    <div className={styles.legendItem}>
      <span className={styles.legendDot} style={{ background: "#eab308" }} />
      <span>Normal (30-70% de recuerdos vivos)</span>
    </div>
    <div className={styles.legendItem}>
      <span className={styles.legendDot} style={{ background: "#ef4444" }} />
      <span>En reposo (menos de 30% de recuerdos vivos)</span>
    </div>
    <div className={styles.legendDivider} />
    <div className={styles.legendItem}>
      <span className={styles.legendIcon}>💡</span>
      <span>Cada punto es una medición del cerebro</span>
    </div>
    <div className={styles.legendItem}>
      <span className={styles.legendIcon}>🧠</span>
      <span>Los recuerdos son los nodos tocados en ese momento</span>
    </div>
  </div>
);

export const EnergyLineChart = ({
  data,
  ciclos,
  height = 280,
  onPointClick,
}: EnergyLineChartProps) => {
  if (!data || data.length === 0) {
    return <div className={styles.empty}>Sin datos</div>;
  }

  const chartData = useMemo(() => {
    if (!ciclos || ciclos.length === 0) {
      return data.map((d) => ({
        ...d,
        label: formatDate(d.timestamp),
      }));
    }
    return data.map((d) => {
      const cicloMasCercano = ciclos.reduce(
        (closest: CicloActividad, c: CicloActividad) => {
          return Math.abs(c.timestamp - d.timestamp) <
            Math.abs(closest.timestamp - d.timestamp)
            ? c
            : closest;
        },
        ciclos[0] as CicloActividad,
      );
      return {
        ...d,
        label: formatDate(d.timestamp),
        categoria_dominante: cicloMasCercano?.categoria_dominante ?? d.categoria_dominante ?? "N/A",
      };
    });
  }, [data, ciclos]);

  const handleClick = (state: any) => {
    if (
      state?.activeTooltipIndex !== undefined &&
      state.activeTooltipIndex >= 0 &&
      onPointClick
    ) {
      const point = chartData[state.activeTooltipIndex];
      onPointClick(point as EnergyPoint);
    }
  };

  return (
    <div className={styles.chartWrapper}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={chartData}
          margin={{ top: 5, right: 10, left: 25, bottom: 0 }}
          cursor="pointer"
          onClick={handleClick}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--border-color)"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--text-muted)", fontSize: 17, dy: 11 }}
            stroke="var(--border-color)"
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "var(--text-muted)", fontSize: 17 }}
            tickFormatter={(v) => v.toFixed(0)}
            stroke="var(--border-color)"
            style={{ marginTop: 14 }}
            width={55}
            label={{
              value: "Energía",
              angle: -90,
              position: "insideLeft",
              offset: 0,
              style: {
                fill: "var(--accent-color)",
                fontWeight: 500,
                textAnchor: "middle",
              },
            }}
          />

          <Tooltip
            content={<CustomTooltip />}
            wrapperStyle={{ zIndex: 100, outline: "none" }}
            position={{ y: -100 }}
            reverseDirection={{ x: true }}
          />
          <Legend content={<ChartLegend />} wrapperStyle={{ paddingTop: '20px' }}  />
          <Line
            type="monotone"
            dataKey="energia"
            name="Energía"
            stroke="var(--accent-color)"
            strokeWidth={2}
            dot={{
              r: 4,
              strokeWidth: 2,
              fill: "var(--accent-color)",
            }}
            activeDot={{ r: 6, stroke: "#fff", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default EnergyLineChart;
