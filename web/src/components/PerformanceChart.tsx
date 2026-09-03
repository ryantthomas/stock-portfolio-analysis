import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { usePrefersDark } from "../hooks/useTheme";
import { paletteFor } from "../lib/palette";
import { percent, shortDate, number } from "../lib/format";
import type { DrawdownPoint, SeriesPoint } from "../lib/types";

interface Props {
  performance: SeriesPoint[];
  drawdown: DrawdownPoint[];
  benchmark: string;
}

/**
 * Growth curve and drawdown path.
 *
 * Both series are indexed to 100 at the start of the window so they share one
 * y-axis -- a second scale would invent a relationship between them that the
 * data does not contain.
 *
 * Drawdown is a separate panel underneath rather than a second axis on the
 * same plot, for the same reason.
 */
export function PerformanceChart({ performance, drawdown, benchmark }: Props) {
  const dark = usePrefersDark();
  const palette = paletteFor(dark);

  const portfolioColor = palette.categorical[0] as string;
  const benchmarkColor = palette.benchmark;

  if (performance.length === 0) {
    return null;
  }

  const last = performance[performance.length - 1];
  const totalReturn = last ? last.portfolio / 100 - 1 : null;
  const benchReturn = last?.benchmark != null ? last.benchmark / 100 - 1 : null;

  return (
    <section className="card">
      <div className="card-header">
        <h2>Growth of 100</h2>
        <span className="hint">
          {performance.length} trading days · rebalanced daily to target weights
        </span>
      </div>

      <div className="card-body">
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={performance}
              margin={{ top: 6, right: 12, bottom: 0, left: 0 }}
            >
              <CartesianGrid stroke={palette.grid} vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={shortDate}
                stroke={palette.axis}
                tick={{ fontSize: 11 }}
                minTickGap={44}
                tickLine={false}
                axisLine={{ stroke: palette.grid }}
              />
              <YAxis
                stroke={palette.axis}
                tick={{ fontSize: 11 }}
                width={46}
                tickLine={false}
                axisLine={false}
                domain={["auto", "auto"]}
              />
              <Tooltip content={<GrowthTooltip benchmark={benchmark} />} />
              {/* Benchmark is drawn first so the portfolio line sits on top. */}
              <Line
                type="monotone"
                dataKey="benchmark"
                name={benchmark}
                stroke={benchmarkColor}
                strokeWidth={2}
                strokeDasharray="4 3"
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="portfolio"
                name="Portfolio"
                stroke={portfolioColor}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Legend plus direct end-of-series labels: identity is never carried
            by color alone. */}
        <div className="legend-row">
          <span className="item">
            <span className="swatch" style={{ background: portfolioColor }} />
            Portfolio {totalReturn !== null && `· ${percent(totalReturn, 1)}`}
          </span>
          <span className="item">
            <span
              className="swatch"
              style={{
                background: `repeating-linear-gradient(90deg, ${benchmarkColor} 0 4px, transparent 4px 7px)`,
              }}
            />
            {benchmark} {benchReturn !== null && `· ${percent(benchReturn, 1)}`}
          </span>
        </div>
      </div>

      {drawdown.length > 0 && (
        <>
          <div className="card-header" style={{ borderTop: "1px solid var(--border)" }}>
            <h3>Drawdown</h3>
            <span className="hint">Percent below the running peak</span>
          </div>
          <div className="card-body">
            <div className="chart-wrap short">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={drawdown}
                  margin={{ top: 6, right: 12, bottom: 0, left: 0 }}
                >
                  <defs>
                    <linearGradient id="drawdownFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={palette.divergingPositive} stopOpacity={0.05} />
                      <stop offset="100%" stopColor={palette.divergingPositive} stopOpacity={0.32} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={palette.grid} vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={shortDate}
                    stroke={palette.axis}
                    tick={{ fontSize: 11 }}
                    minTickGap={44}
                    tickLine={false}
                    axisLine={{ stroke: palette.grid }}
                  />
                  <YAxis
                    stroke={palette.axis}
                    tick={{ fontSize: 11 }}
                    width={46}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value: number) => `${(value * 100).toFixed(0)}%`}
                  />
                  <Tooltip content={<DrawdownTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="drawdown"
                    stroke={palette.divergingPositive}
                    strokeWidth={2}
                    fill="url(#drawdownFill)"
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

interface TooltipProps {
  active?: boolean;
  label?: string | number;
  payload?: { name?: string; value?: number; dataKey?: string }[];
}

function GrowthTooltip({
  active,
  label,
  payload,
  benchmark,
}: TooltipProps & { benchmark: string }) {
  if (!active || !payload?.length) return null;

  const portfolio = payload.find((p) => p.dataKey === "portfolio")?.value;
  const bench = payload.find((p) => p.dataKey === "benchmark")?.value;

  return (
    <div className="tooltip">
      <div className="head">{String(label)}</div>
      {portfolio !== undefined && (
        <div className="row">
          <span>Portfolio</span>
          <span>
            {number(portfolio, 1)} ({percent(portfolio / 100 - 1, 1)})
          </span>
        </div>
      )}
      {bench !== undefined && bench !== null && (
        <div className="row">
          <span>{benchmark}</span>
          <span>
            {number(bench, 1)} ({percent(bench / 100 - 1, 1)})
          </span>
        </div>
      )}
    </div>
  );
}

function DrawdownTooltip({ active, label, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const value = payload[0]?.value;
  return (
    <div className="tooltip">
      <div className="head">{String(label)}</div>
      <div className="row">
        <span>Below peak</span>
        <span>{percent(value ?? null, 2)}</span>
      </div>
    </div>
  );
}
