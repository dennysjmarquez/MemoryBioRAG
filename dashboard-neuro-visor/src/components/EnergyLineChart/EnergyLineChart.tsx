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

interface EnergyPoint {
  timestamp: number;
  energia: number;
  total_nodos: number;
  dormidos: number;
  activos: number;
  latencia_ms: number;
}

interface EnergyLineChartProps {
  title: string;
  data: EnergyPoint[];
  height?: number;
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

const CustomTooltip = ({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: any; value: number }>;
}) => {
  if (!active || !payload || !payload[0]) return null;

  const point = payload[0].payload as EnergyPoint;

  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipRow}>
        <span className={styles.tooltipLabel}>📅 Fecha:</span>
        <span className={styles.tooltipValue}>
          {formatDate(point.timestamp)}
        </span>
      </div>
      <div className={styles.tooltipDesc}>Cuándo se tomó esta medición</div>

      <div className={styles.tooltipRow}>
        <span className={styles.tooltipLabel}>⚡ Fuerza de conexiones:</span>
        <span className={styles.tooltipValue}>{point.energia.toFixed(2)}</span>
      </div>
      <div className={styles.tooltipDesc}>
        Qué tan fácil le es al cerebro conectar recuerdos entre sí
      </div>

      <div className={styles.tooltipRow}>
        <span className={styles.tooltipLabel}>🧠 Recuerdos activos:</span>
        <span className={styles.tooltipValue}>{point.activos}</span>
      </div>
      <div className={styles.tooltipDesc}>
        Recuerdos que el cerebro está usando ahora
      </div>

      <div className={styles.tooltipRow}>
        <span className={styles.tooltipLabel}>🌙 Recuerdos dormidos:</span>
        <span className={styles.tooltipValue}>{point.dormidos}</span>
      </div>
      <div className={styles.tooltipDesc}>
        Recuerdos que se apagaron por no usarse
      </div>

      <div className={styles.tooltipRow}>
        <span className={styles.tooltipLabel}>📊 Total de recuerdos:</span>
        <span className={styles.tooltipValue}>{point.total_nodos}</span>
      </div>
      <div className={styles.tooltipDesc}>
        Todo lo que el cerebro tiene guardado
      </div>

      <div className={styles.tooltipRow}>
        <span className={styles.tooltipLabel}>⏱️ Velocidad de búsqueda:</span>
        <span className={styles.tooltipValue}>{point.latencia_ms} ms</span>
      </div>
      <div className={styles.tooltipDesc}>
        Cuánto tarda el cerebro en encontrar un recuerdo
      </div>
    </div>
  );
};

export const EnergyLineChart = ({
  title,
  data,
  height = 280,
}: EnergyLineChartProps) => {
  if (!data || data.length === 0) {
    return <div className={styles.empty}>Sin datos</div>;
  }

  const chartData = useMemo(
    () =>
      data.map((d) => ({
        ...d,
        label: formatDate(d.timestamp),
      })),
    [data],
  );

  return (
    <div className={styles.chartWrapper}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={chartData}
          margin={{ top: 5, right: 10, left: 25, bottom: 0 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--border-color)"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--text-muted)", fontSize: 13 }}
            stroke="var(--border-color)"
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "var(--text-muted)", fontSize: 13 }}
            tickFormatter={(v) => v.toFixed(0)}
            stroke="var(--border-color)"
            width={55}
            label={{
              value: "Fuerza de conexiones",
              angle: -90,
              position: "insideLeft",
              offset: 0,
              style: {
                fill: "var(--accent-color)",
                fontSize: 14,
                fontWeight: 500,
                textAnchor: "middle",
                strokeWidth: 2,
              },
            }}
          />

          <Tooltip
            content={<CustomTooltip />}
            wrapperStyle={{ zIndex: 100, outline: "none" }}
            position={{ y: -100 }} // Lo mantiene fijo arriba en el eje Y para que no tape la línea
            reverseDirection={{ x: true }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="energia"
            name="Puntos de dato"
            stroke="var(--accent-color)"
            strokeWidth={2}
            dot={{ r: 4, strokeWidth: 2, fill: "var(--accent-color)" }}
            activeDot={{ r: 6, stroke: "#fff", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default EnergyLineChart;
