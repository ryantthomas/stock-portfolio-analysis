import { number, percent, signedPercent } from "../lib/format";
import type { RiskMetrics as RiskMetricsType } from "../lib/types";

interface Props {
  risk: RiskMetricsType;
  benchmarkRisk: RiskMetricsType;
  benchmark: string;
}

/** Headline risk and return figures, each shown against the benchmark. */
export function RiskMetrics({ risk, benchmarkRisk, benchmark }: Props) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>Risk &amp; return</h2>
        <span className="hint">vs {benchmark}</span>
      </div>

      <div className="metric-grid">
        <Metric
          label="Annual return"
          value={signedPercent(risk.annual_return)}
          sub={`${benchmark} ${signedPercent(benchmarkRisk.annual_return)}`}
          tone={toneOf(risk.annual_return)}
        />
        <Metric
          label="Volatility"
          value={percent(risk.annual_vol)}
          sub={`${benchmark} ${percent(benchmarkRisk.annual_vol)}`}
        />
        <Metric
          label="Sharpe ratio"
          value={number(risk.sharpe)}
          sub={`${benchmark} ${number(benchmarkRisk.sharpe)}`}
          tone={toneOf(risk.sharpe)}
        />
        <Metric
          label="Sortino ratio"
          value={number(risk.sortino)}
          sub="downside risk only"
          tone={toneOf(risk.sortino)}
        />
        <Metric
          label="Max drawdown"
          value={percent(risk.max_drawdown)}
          sub={`${benchmark} ${percent(benchmarkRisk.max_drawdown)}`}
          tone="negative"
        />
        <Metric
          label="Beta"
          value={number(risk.beta)}
          sub={betaVerdict(risk.beta, benchmark)}
        />
        <Metric
          label="Alpha"
          value={signedPercent(risk.alpha)}
          sub="annualized, risk-adjusted"
          tone={toneOf(risk.alpha)}
        />
        <Metric
          label="Daily VaR (95%)"
          value={percent(risk.var_95, 2)}
          sub={`worst 5% average ${percent(risk.cvar_95, 2)}`}
          tone="negative"
        />
        <Metric
          label="Positive days"
          value={percent(risk.positive_days, 1)}
          sub={`best ${signedPercent(risk.best_day, 1)} / worst ${signedPercent(risk.worst_day, 1)}`}
        />
        <Metric
          label="Tracking error"
          value={percent(risk.tracking_error)}
          sub={`deviation from ${benchmark}`}
        />
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "positive" | "negative";
}) {
  return (
    <div className="metric">
      <div className="label">{label}</div>
      <div className={`value${tone ? ` ${tone}` : ""}`}>{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

function toneOf(value: number | null): "positive" | "negative" | undefined {
  if (value === null) return undefined;
  return value >= 0 ? "positive" : "negative";
}

function betaVerdict(beta: number | null, benchmark: string): string {
  if (beta === null) return "—";
  if (beta > 1.1) return `more volatile than ${benchmark}`;
  if (beta < 0.9) return `less volatile than ${benchmark}`;
  return `moves with ${benchmark}`;
}
