import { gradeColor } from "../lib/palette";
import { number, percent } from "../lib/format";
import type { DiversificationMetrics } from "../lib/types";

/** Human-readable names for the score's weighted components. */
const COMPONENT_LABELS: Record<string, string> = {
  position_breadth: "Position breadth",
  concentration: "Concentration",
  correlation: "Low correlation",
  sector_spread: "Sector spread",
  asset_class_breadth: "Asset class breadth",
};

interface Props {
  metrics: DiversificationMetrics;
}

/**
 * The headline diversification score, shown with the components it is built
 * from. Displaying the parts is the point -- a single opaque number would not
 * tell a user which lever to pull.
 */
export function DiversificationScore({ metrics }: Props) {
  const color = gradeColor(metrics.grade);

  // Dial geometry: a 270-degree arc, leaving a gap at the bottom.
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const arcFraction = 0.75;
  const arcLength = circumference * arcFraction;
  const filled = (metrics.score / 100) * arcLength;

  return (
    <section className="card">
      <div className="card-header">
        <h2>Diversification</h2>
        <span className="hint">
          {metrics.holdings_count} holdings · {metrics.sector_count} sectors
        </span>
      </div>

      <div className="card-body">
        <div className="score-panel">
          <div className="score-dial">
            <svg width="104" height="104" viewBox="0 0 104 104" role="img"
                 aria-label={`Diversification score ${metrics.score.toFixed(0)} out of 100, grade ${metrics.grade}`}>
              {/* Rotated so the arc gap sits at the bottom of the dial. */}
              <g transform="rotate(135 52 52)">
                <circle
                  cx="52" cy="52" r={radius}
                  fill="none" stroke="var(--surface-3)" strokeWidth="9"
                  strokeDasharray={`${arcLength} ${circumference}`}
                  strokeLinecap="round"
                />
                <circle
                  cx="52" cy="52" r={radius}
                  fill="none" stroke={color} strokeWidth="9"
                  strokeDasharray={`${filled} ${circumference}`}
                  strokeLinecap="round"
                  style={{ transition: "stroke-dasharray 0.5s ease" }}
                />
              </g>
            </svg>
            <div className="readout">
              <span className="num" style={{ color }}>
                {metrics.score.toFixed(0)}
              </span>
              <span className="grade">Grade {metrics.grade}</span>
            </div>
          </div>

          <div className="score-components">
            {Object.entries(metrics.components).map(([key, value]) => (
              <div className="component" key={key}>
                <span className="name">{COMPONENT_LABELS[key] ?? key}</span>
                <span className="track">
                  <span
                    style={{
                      width: `${Math.min(100, Math.max(0, value * 100))}%`,
                      // Each bar is colored by its own strength. Painting them
                      // all with the overall grade would make a strong
                      // component look like a weakness.
                      background: componentColor(value),
                    }}
                  />
                </span>
                <span className="pct">{(value * 100).toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="metric-grid">
        <Metric
          label="Effective holdings"
          value={number(metrics.effective_holdings, 1)}
          sub={`of ${metrics.holdings_count} positions`}
        />
        <Metric
          label="Largest position"
          value={percent(metrics.top_weight, 1)}
          sub={`top 5: ${percent(metrics.top5_weight, 0)}`}
        />
        <Metric
          label="Avg correlation"
          value={number(metrics.avg_correlation, 2)}
          sub={correlationVerdict(metrics.avg_correlation)}
        />
        <Metric
          label="Diversification ratio"
          value={number(metrics.diversification_ratio, 2)}
          sub={metrics.diversification_ratio ? "1.00 = no benefit" : "needs 2+ holdings"}
        />
      </div>
    </section>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="metric">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

/** Traffic-light tone for a single 0-1 score component. */
function componentColor(value: number): string {
  if (value >= 0.7) return "var(--positive)";
  if (value >= 0.45) return "var(--info)";
  if (value >= 0.25) return "var(--warning)";
  return "var(--critical)";
}

function correlationVerdict(value: number | null): string {
  if (value === null) return "needs 2+ holdings";
  if (value > 0.8) return "moves as one";
  if (value > 0.6) return "highly linked";
  if (value > 0.35) return "moderately linked";
  return "well spread";
}
