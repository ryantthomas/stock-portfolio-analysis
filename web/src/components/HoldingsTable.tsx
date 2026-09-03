import { useMemo, useState } from "react";

import { compact, currency, percent, signedPercent } from "../lib/format";
import type { HoldingDetail } from "../lib/types";

type SortKey =
  | "weight"
  | "return_1y"
  | "annual_vol"
  | "contribution_to_return"
  | "contribution_to_risk";

interface Props {
  holdings: HoldingDetail[];
}

const COLUMNS: { key: SortKey; label: string; title: string }[] = [
  { key: "weight", label: "Weight", title: "Share of the portfolio" },
  { key: "return_1y", label: "Return", title: "Total return over the analysis window" },
  { key: "annual_vol", label: "Volatility", title: "Annualized standard deviation" },
  {
    key: "contribution_to_return",
    label: "Return contrib.",
    title: "Weight times return: how much of the portfolio's result this position produced",
  },
  {
    key: "contribution_to_risk",
    label: "Risk contrib.",
    title: "Share of total portfolio risk, accounting for correlation with everything else",
  },
];

/**
 * Per-position detail.
 *
 * The two contribution columns are the interesting ones: a position can be 5%
 * of the weight and 15% of the risk, which is invisible from weights alone.
 */
export function HoldingsTable({ holdings }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("weight");
  const [descending, setDescending] = useState(true);

  const sorted = useMemo(() => {
    return [...holdings].sort((a, b) => {
      const left = a[sortKey] ?? -Infinity;
      const right = b[sortKey] ?? -Infinity;
      return descending ? right - left : left - right;
    });
  }, [holdings, sortKey, descending]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setDescending((value) => !value);
    } else {
      setSortKey(key);
      setDescending(true);
    }
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2>Positions</h2>
        <span className="hint">Risk contribution accounts for correlation</span>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th className="left">Holding</th>
              <th className="left">Sector</th>
              {COLUMNS.map((column) => (
                <th key={column.key}>
                  <button
                    type="button"
                    className="ghost"
                    title={column.title}
                    onClick={() => toggleSort(column.key)}
                    style={{ padding: 0, font: "inherit", color: "inherit" }}
                  >
                    {column.label}
                    {sortKey === column.key ? (descending ? " ↓" : " ↑") : ""}
                  </button>
                </th>
              ))}
              <th>Price</th>
              <th>Mkt cap</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((holding) => (
              <tr key={holding.ticker}>
                <td className="left">
                  <div className="sym">{holding.ticker}</div>
                  <div className="name">{holding.name ?? ""}</div>
                </td>
                <td className="left">
                  <span className="badge">{holding.sector}</span>
                </td>
                <td className="num">{percent(holding.weight)}</td>
                <td
                  className="num"
                  style={{ color: toneColor(holding.return_1y) }}
                >
                  {signedPercent(holding.return_1y)}
                </td>
                <td className="num">{percent(holding.annual_vol)}</td>
                <td
                  className="num"
                  style={{ color: toneColor(holding.contribution_to_return) }}
                >
                  {signedPercent(holding.contribution_to_return)}
                </td>
                <td className="num">
                  <RiskShare
                    share={holding.contribution_to_risk}
                    weight={holding.weight}
                  />
                </td>
                <td className="num">{currency(holding.last_price)}</td>
                <td className="num">{compact(holding.market_cap)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/**
 * Risk share, flagged when it materially exceeds the position's weight --
 * the case where a small holding is quietly driving portfolio volatility.
 */
function RiskShare({ share, weight }: { share: number | null; weight: number }) {
  if (share === null) return <>—</>;
  const outsized = share > weight * 1.25;
  return (
    <span
      title={
        outsized
          ? `Contributes ${percent(share)} of risk on ${percent(weight)} of the weight`
          : undefined
      }
      style={{ color: outsized ? "var(--warning)" : undefined }}
    >
      {percent(share)}
      {outsized ? " ▲" : ""}
    </span>
  );
}

function toneColor(value: number | null): string | undefined {
  if (value === null) return undefined;
  return value >= 0 ? "var(--positive)" : "var(--critical)";
}
