import { severityColor } from "../lib/palette";
import type { Opportunity } from "../lib/types";

interface Props {
  opportunities: Opportunity[];
}

const SEVERITY_LABEL: Record<string, string> = {
  critical: "Critical",
  warning: "Worth reviewing",
  info: "Note",
};

/**
 * Findings about the shape of the allocation, ordered by severity.
 *
 * Each card names the metric that triggered it so the user can judge relevance
 * themselves. These describe structure, not recommendations to trade.
 */
export function Opportunities({ opportunities }: Props) {
  if (opportunities.length === 0) {
    return (
      <section className="card">
        <div className="card-header">
          <h2>Findings</h2>
        </div>
        <div className="card-body">
          <div className="notice info">
            No concentration, correlation or allocation flags triggered for this
            portfolio.
          </div>
        </div>
      </section>
    );
  }

  const counts = opportunities.reduce<Record<string, number>>((acc, item) => {
    acc[item.severity] = (acc[item.severity] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <section className="card">
      <div className="card-header">
        <h2>Findings</h2>
        <span className="hint">
          {counts.critical ? `${counts.critical} critical · ` : ""}
          {counts.warning ? `${counts.warning} to review · ` : ""}
          {counts.info ?? 0} notes
        </span>
      </div>

      <div className="opportunity-list">
        {opportunities.map((opportunity) => {
          const color = severityColor(opportunity.severity);
          return (
            <article
              className="opportunity"
              key={opportunity.id}
              style={{ borderLeftColor: color }}
            >
              <span className="dot" style={{ background: color }} aria-hidden="true" />
              <div className="content">
                <div className="title">{opportunity.title}</div>
                <div className="detail">{opportunity.detail}</div>
                <div className="tags">
                  <span className="badge" style={{ color }}>
                    {SEVERITY_LABEL[opportunity.severity] ?? opportunity.severity}
                  </span>
                  <span className="badge">{opportunity.kind}</span>
                  {opportunity.tickers.map((ticker) => (
                    <span className="badge mono" key={ticker}>
                      {ticker}
                    </span>
                  ))}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
