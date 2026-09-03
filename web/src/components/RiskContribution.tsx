import { usePrefersDark } from "../hooks/useTheme";
import { categorical, paletteFor } from "../lib/palette";
import { percent } from "../lib/format";
import type { HoldingDetail } from "../lib/types";

interface Props {
  holdings: HoldingDetail[];
}

/**
 * Weight against risk contribution, position by position.
 *
 * This is the chart that answers "where is my risk actually coming from".
 * A position whose risk bar runs past its weight bar is punching above its
 * size -- usually because it is volatile, correlated with everything else, or
 * both. Two paired bars per row rather than a stacked or dual-axis form, so
 * the comparison is a direct length comparison on one shared scale.
 */
export function RiskContribution({ holdings }: Props) {
  const dark = usePrefersDark();
  const palette = paletteFor(dark);

  const rows = holdings
    .filter((h) => h.contribution_to_risk !== null)
    .sort((a, b) => (b.contribution_to_risk ?? 0) - (a.contribution_to_risk ?? 0));

  if (rows.length === 0) return null;

  const max = Math.max(
    ...rows.map((h) => Math.max(h.weight, h.contribution_to_risk ?? 0)),
    0.01,
  );

  const weightColor = categorical(palette, 0);
  const riskColor = categorical(palette, 1);

  return (
    <section className="card">
      <div className="card-header">
        <h2>Weight vs risk contribution</h2>
        <span className="hint">Risk accounts for volatility and correlation</span>
      </div>

      <div className="card-body">
        <div className="legend-row" style={{ marginTop: 0, marginBottom: 14 }}>
          <span className="item">
            <span className="swatch" style={{ background: weightColor }} />
            Share of capital
          </span>
          <span className="item">
            <span className="swatch" style={{ background: riskColor }} />
            Share of risk
          </span>
        </div>

        <div className="contrib-list">
          {rows.map((holding) => {
            const risk = holding.contribution_to_risk ?? 0;
            const outsized = risk > holding.weight * 1.25;
            return (
              <div className="contrib-row" key={holding.ticker}>
                <span className="contrib-ticker">
                  {holding.ticker}
                  {outsized && (
                    <span
                      className="contrib-flag"
                      title="Contributes more risk than its size would suggest"
                    >
                      ▲
                    </span>
                  )}
                </span>
                <span className="contrib-bars">
                  <span className="contrib-bar">
                    <span
                      style={{
                        width: `${(holding.weight / max) * 100}%`,
                        background: weightColor,
                      }}
                    />
                  </span>
                  <span className="contrib-bar">
                    <span
                      style={{
                        width: `${(risk / max) * 100}%`,
                        background: riskColor,
                      }}
                    />
                  </span>
                </span>
                <span className="contrib-values">
                  <span>{percent(holding.weight, 1)}</span>
                  <span style={{ color: outsized ? "var(--warning)" : undefined }}>
                    {percent(risk, 1)}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
