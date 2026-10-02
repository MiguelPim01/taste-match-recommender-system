import { useState, type ReactNode } from "react";

import type { MinuteCount, ModelVersion, Signal } from "../api";
import { formatInteger, formatMetric, formatShortClock } from "../format";

// Bottom-to-top stacking order. It is the adjacency order that passed the colour-vision check
// (dataviz validate_palette.js: blue, orange, aqua), so do not reorder it.
export const SERIES: { key: Signal; label: string; color: string }[] = [
  { key: "views", label: "Visualizações", color: "var(--view)" },
  { key: "reviews", label: "Avaliações", color: "var(--review)" },
  { key: "comments", label: "Comentários", color: "var(--comment)" },
];

const WIDTH = 640;
const HEIGHT = 220;
const PAD = { top: 14, right: 12, bottom: 30, left: 44 };
const PLOT_W = WIDTH - PAD.left - PAD.right;
const PLOT_H = HEIGHT - PAD.top - PAD.bottom;
const GAP = 2;

function niceCeiling(value: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 5, 10].find((candidate) => candidate * magnitude >= value) ?? 10;
  return step * magnitude;
}

function roundedTop(x: number, y: number, width: number, height: number, radius = 4): string {
  const r = Math.min(radius, height, width / 2);
  return `M${x},${y + height}V${y + r}Q${x},${y} ${x + r},${y}H${x + width - r}Q${x + width},${y} ${x + width},${y + r}V${y + height}Z`;
}

export function Legend({ items }: { items: { label: string; color: string; shape: "rect" | "line" }[] }) {
  return (
    <ul className="legend">
      {items.map((item) => (
        <li key={item.label}>
          <svg width="14" height="10" aria-hidden="true">
            {item.shape === "rect"
              ? <rect width="14" height="10" rx="2" fill={item.color} />
              : <line x1="0" y1="5" x2="14" y2="5" stroke={item.color} strokeWidth="2" strokeLinecap="round" />}
          </svg>
          {item.label}
        </li>
      ))}
    </ul>
  );
}

export function ChartFrame({ legend, table, children }: { legend?: ReactNode; table: ReactNode; children: ReactNode }) {
  const [asTable, setAsTable] = useState(false);
  return (
    <div className="chart">
      <div className="chart-head">
        {legend ?? <span />}
        <button type="button" className="link-button" onClick={() => setAsTable((value) => !value)}>
          {asTable ? "Ver gráfico" : "Ver tabela"}
        </button>
      </div>
      {asTable ? <div className="chart-table">{table}</div> : <div className="chart-plot">{children}</div>}
    </div>
  );
}

function Tooltip({ left, title, rows }: { left: number; title: string; rows: { value: string; label: string; color?: string }[] }) {
  return (
    <div className="tooltip" style={{ left: `${Math.min(86, Math.max(14, (left / WIDTH) * 100))}%` }} role="status">
      <p className="tooltip-title">{title}</p>
      {rows.map((row) => (
        <p key={row.label} className="tooltip-row">
          {row.color && <span className="tooltip-key" style={{ background: row.color }} />}
          <strong>{row.value}</strong> {row.label}
        </p>
      ))}
    </div>
  );
}

/** Events published per minute, stacked by type. Each minute column is its own hover and focus target. */
export function MinuteColumns({ data }: { data: MinuteCount[] }) {
  const [active, setActive] = useState<number | null>(null);
  const totals = data.map((minute) => SERIES.reduce((sum, series) => sum + minute[series.key], 0));
  const max = niceCeiling(Math.max(...totals, 4));
  const band = PLOT_W / data.length;
  const barWidth = Math.min(24, band * 0.62);
  const y = (value: number) => PAD.top + PLOT_H - (value / max) * PLOT_H;
  const labelled = new Set([0, Math.floor((data.length - 1) / 2), data.length - 1]);

  const table = (
    <table>
      <thead><tr><th>Minuto</th>{SERIES.map((series) => <th key={series.key}>{series.label}</th>)}</tr></thead>
      <tbody>
        {data.map((minute) => (
          <tr key={minute.minute}>
            <td>{formatShortClock(minute.minute)}</td>
            {SERIES.map((series) => <td key={series.key}>{formatInteger(minute[series.key])}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <ChartFrame legend={<Legend items={SERIES.map((series) => ({ ...series, shape: "rect" }))} />} table={table}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img"
        aria-label={`Eventos por minuto nos últimos ${data.length} minutos; o maior minuto teve ${formatInteger(Math.max(...totals))}.`}>
        {[0, max / 2, max].filter(Number.isInteger).map((tick) => (
          <g key={tick}>
            <line className="grid" x1={PAD.left} x2={WIDTH - PAD.right} y1={y(tick)} y2={y(tick)} />
            <text className="axis" x={PAD.left - 8} y={y(tick) + 4} textAnchor="end">{formatInteger(tick)}</text>
          </g>
        ))}
        {data.map((minute, index) => {
          const x = PAD.left + band * index + (band - barWidth) / 2;
          const present = SERIES.filter((series) => minute[series.key] > 0);
          let base = 0;
          return (
            <g key={minute.minute} className={active === index ? "column column-active" : "column"}>
              {present.map((series, position) => {
                const top = y(base + minute[series.key]);
                const bottom = y(base);
                base += minute[series.key];
                const isTop = position === present.length - 1;
                return (
                  <g key={series.key}>
                    {isTop
                      ? <path d={roundedTop(x, top, barWidth, bottom - top)} fill={series.color} />
                      : <rect x={x} y={top} width={barWidth} height={bottom - top} fill={series.color} />}
                    {position > 0 && <line className="segment-gap" x1={x} x2={x + barWidth} y1={bottom} y2={bottom} strokeWidth={GAP} />}
                  </g>
                );
              })}
              {labelled.has(index) && (
                <text className="axis" x={x + barWidth / 2} y={HEIGHT - 8} textAnchor="middle">{formatShortClock(minute.minute)}</text>
              )}
              <rect
                className="hit"
                x={PAD.left + band * index}
                y={PAD.top}
                width={band}
                height={PLOT_H}
                tabIndex={0}
                aria-label={`${formatShortClock(minute.minute)}: ${SERIES.map((series) => `${minute[series.key]} ${series.label.toLowerCase()}`).join(", ")}`}
                onPointerEnter={() => setActive(index)}
                onPointerLeave={() => setActive(null)}
                onFocus={() => setActive(index)}
                onBlur={() => setActive(null)}
              />
            </g>
          );
        })}
      </svg>
      {active !== null && (
        <Tooltip
          left={PAD.left + band * (active + 0.5)}
          title={formatShortClock(data[active].minute)}
          rows={[...SERIES].reverse().map((series) => ({
            value: formatInteger(data[active][series.key]), label: series.label.toLowerCase(), color: series.color,
          }))}
        />
      )}
    </ChartFrame>
  );
}

/** NDCG@10 of each model, oldest to newest. One series, so the heading names it and there is no legend. */
export function ModelTrend({ models }: { models: ModelVersion[] }) {
  const [active, setActive] = useState<number | null>(null);
  const points = [...models].reverse();
  if (points.length === 0) return <p className="quiet">Nenhum modelo treinado ainda.</p>;

  const values = points.map((model) => model.metric_value);
  const low = Math.floor((Math.min(...values) - 0.02) * 20) / 20;
  const high = Math.ceil((Math.max(...values) + 0.02) * 20) / 20;
  const x = (index: number) => PAD.left + (points.length === 1 ? PLOT_W / 2 : (index / (points.length - 1)) * PLOT_W);
  const y = (value: number) => PAD.top + PLOT_H - ((value - low) / (high - low)) * PLOT_H;
  const path = points.map((model, index) => `${index ? "L" : "M"}${x(index)},${y(model.metric_value)}`).join("");
  const last = points.length - 1;

  const table = (
    <table>
      <thead><tr><th>Modelo</th><th>NDCG@10</th><th>Eventos usados</th><th>Entrou em uso</th></tr></thead>
      <tbody>
        {models.map((model) => (
          <tr key={model.run_id}>
            <td>{model.run_id.slice(0, 8)}</td>
            <td>{formatMetric(model.metric_value)}</td>
            <td>{formatInteger(model.trained_until_total)}</td>
            <td>{formatShortClock(model.created_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <ChartFrame table={table}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img"
        aria-label={`NDCG@10 de ${points.length} modelos; o atual tem ${formatMetric(values[last])}.`}>
        {[low, (low + high) / 2, high].map((tick) => (
          <g key={tick}>
            <line className="grid" x1={PAD.left} x2={WIDTH - PAD.right} y1={y(tick)} y2={y(tick)} />
            <text className="axis" x={PAD.left - 8} y={y(tick) + 4} textAnchor="end">{formatMetric(tick)}</text>
          </g>
        ))}
        {active !== null && <line className="crosshair" x1={x(active)} x2={x(active)} y1={PAD.top} y2={PAD.top + PLOT_H} />}
        <path d={path} className="trend-line" />
        {points.map((model, index) => (
          <g key={model.run_id}>
            <circle cx={x(index)} cy={y(model.metric_value)} r={4} className="trend-dot" />
            <circle
              className="hit"
              cx={x(index)}
              cy={y(model.metric_value)}
              r={14}
              tabIndex={0}
              aria-label={`Modelo ${model.run_id.slice(0, 8)}: NDCG@10 ${formatMetric(model.metric_value)}`}
              onPointerEnter={() => setActive(index)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(index)}
              onBlur={() => setActive(null)}
            />
          </g>
        ))}
        <text className="end-label" x={x(last)} y={y(values[last]) - 12} textAnchor={points.length === 1 ? "middle" : "end"}>
          {formatMetric(values[last])}
        </text>
        <text className="axis" x={x(0)} y={HEIGHT - 8} textAnchor={points.length === 1 ? "middle" : "start"}>
          {formatShortClock(points[0].created_at)}
        </text>
        {points.length > 1 && (
          <text className="axis" x={x(last)} y={HEIGHT - 8} textAnchor="end">{formatShortClock(points[last].created_at)}</text>
        )}
      </svg>
      {active !== null && (
        <Tooltip
          left={x(active)}
          title={`Modelo ${points[active].run_id.slice(0, 8)}`}
          rows={[
            { value: formatMetric(points[active].metric_value), label: "NDCG@10" },
            { value: formatInteger(points[active].trained_until_total), label: "eventos usados" },
            { value: formatShortClock(points[active].created_at), label: "entrou em uso" },
          ]}
        />
      )}
    </ChartFrame>
  );
}

/** Progress toward the next training: the fill and its lighter track share one hue. */
export function Meter({ value, max, label }: { value: number; max: number; label: string }) {
  return (
    <div className="meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={Math.min(value, max)}>
      <div className="meter-fill" style={{ width: `${Math.min(1, value / max) * 100}%` }} />
    </div>
  );
}
