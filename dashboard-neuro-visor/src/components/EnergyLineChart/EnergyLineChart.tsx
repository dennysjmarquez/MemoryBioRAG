import { useMemo, useCallback } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import styles from "./EnergyLineChart.module.css";
import type { CicloActividad, EnergyPoint } from "../../types";

interface EnergyLineChartProps {
  data: EnergyPoint[];
  ciclos?: CicloActividad[];
  height?: number;
  onPointClick?: (punto: EnergyPoint) => void;
  selectedPoint?: EnergyPoint | null;
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

/** Custom dot renderer: highlights the selected point */
const CustomDot = (props: any) => {
  const { cx, cy, payload, selectedTimestamp } = props;
  if (cx == null || cy == null) return null;

  const isSelected = selectedTimestamp != null && payload?.timestamp === selectedTimestamp;

  if (isSelected) {
    return (
      <g>
        {/* Outer glow ring */}
        <circle cx={cx} cy={cy} r={10} fill="rgba(59, 130, 246, 0.2)" stroke="none" />
        {/* Selected dot */}
        <circle
          cx={cx} cy={cy} r={6}
          fill="#fff"
          stroke="var(--accent-color)"
          strokeWidth={3}
        />
      </g>
    );
  }

  return (
    <circle
      cx={cx} cy={cy} r={4}
      fill="var(--accent-color)"
      stroke="var(--accent-color)"
      strokeWidth={2}
    />
  );
};

export const EnergyLineChart = ({
  data,
  ciclos,
  height = 280,
  onPointClick,
  selectedPoint,
}: EnergyLineChartProps) => {

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
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

  // Use the Recharts onClick on the LineChart, extracting the index
  // from activeTooltipIndex which is highly reliable.
  const handleChartClick = useCallback(
    (state: any) => {
      if (!onPointClick || !state) return;

      const idx = state?.activeTooltipIndex;
      if (idx !== undefined && idx >= 0 && idx < chartData.length) {
        onPointClick(chartData[idx] as EnergyPoint);
      }
    },
    [chartData, onPointClick]
  );

  const selectedTimestamp = selectedPoint?.timestamp ?? null;

  if (!data || data.length === 0) {
    return <div className={styles.empty}>Sin datos</div>;
  }

  return (
    <div className={styles.chartWrapper}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={chartData}
          margin={{ top: 5, right: 25, left: 25, bottom: 5 }}
          cursor="pointer"
          onClick={handleChartClick}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--border-color)"
            vertical={false}
          />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatDate}
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
          />

          {/* Vertical reference line at the selected point */}
          {selectedTimestamp && (
            <ReferenceLine
              x={selectedTimestamp}
              stroke="rgba(255,255,255,0.4)"
              strokeDasharray="4 4"
              strokeWidth={1}
            />
          )}

          <Legend content={<ChartLegend />} wrapperStyle={{ paddingTop: '20px' }}  />
          <Line
            type="monotone"
            dataKey="energia"
            name="Energía"
            stroke="var(--accent-color)"
            strokeWidth={2}
            dot={<CustomDot selectedTimestamp={selectedTimestamp} />}
            activeDot={{ r: 6, stroke: "#fff", strokeWidth: 2, cursor: "pointer" }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default EnergyLineChart;

