import { useState } from "react";

import type { CategoryActivity } from "../api";
import { iconFor } from "../categories";
import { formatInteger, plural } from "../format";
import { ChartFrame, Legend, SERIES } from "./charts";
import { Icon } from "./Icon";

const SHOWN = 12;

/** Interactions per category, longest bar first, each bar stacked by event type in the validated order. */
export function CategoryChart({ rows }: { rows: CategoryActivity[] }) {
  const [active, setActive] = useState<string | null>(null);
  const shown = rows.slice(0, SHOWN);
  const max = Math.max(...shown.map((row) => row.total), 1);

  const table = (
    <table>
      <thead>
        <tr><th>Categoria</th>{SERIES.map((series) => <th key={series.key}>{series.label}</th>)}<th>Total</th></tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.category}>
            <td>{row.category}</td>
            {SERIES.map((series) => <td key={series.key}>{formatInteger(row[series.key])}</td>)}
            <td>{formatInteger(row.total)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <ChartFrame legend={<Legend items={SERIES.map((series) => ({ ...series, shape: "rect" }))} />} table={table}>
      <ol className="bars" aria-label="Interações por categoria">
        {shown.map((row) => {
          const share = row.total / max;
          const icon = iconFor(row.category);
          return (
            <li
              key={row.category}
              className="bar-row"
              tabIndex={0}
              aria-label={`${row.category}: ${plural(row.total, "interação", "interações")}, sendo ${
                SERIES.map((series) => `${formatInteger(row[series.key])} ${series.label.toLowerCase()}`).join(", ")}`}
              onPointerEnter={() => setActive(row.category)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(row.category)}
              onBlur={() => setActive(null)}
            >
              <span className="bar-label">
                {icon ? <Icon name={icon} size={16} /> : <span className="bar-icon-space" />}
                <span className="bar-name">{row.category}</span>
              </span>
              <div className="bar-track">
                <span className="bar" style={{ width: `calc((100% - 48px) * ${share})` }}>
                  {SERIES.filter((series) => row[series.key] > 0).map((series) => (
                    <span key={series.key} className="bar-segment" style={{ flexGrow: row[series.key], background: series.color }} />
                  ))}
                </span>
                <span className="bar-value">{formatInteger(row.total)}</span>
                {active === row.category && (
                  <div className="tooltip tooltip-above" style={{ left: `${Math.min(80, Math.max(20, share * 100))}%` }} aria-hidden="true">
                    <p className="tooltip-title">{row.category}</p>
                    {SERIES.map((series) => (
                      <p key={series.key} className="tooltip-row">
                        <span className="tooltip-key" style={{ background: series.color }} />
                        <strong>{formatInteger(row[series.key])}</strong> {series.label.toLowerCase()}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {rows.length > SHOWN && (
        <p className="quiet chart-after">Mais {plural(rows.length - SHOWN, "categoria", "categorias")} na tabela.</p>
      )}
    </ChartFrame>
  );
}
