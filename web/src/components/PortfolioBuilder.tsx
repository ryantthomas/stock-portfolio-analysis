import { TickerInput } from "./TickerInput";
import { PRESETS } from "../lib/presets";
import type { HoldingInput } from "../lib/types";

interface Props {
  holdings: HoldingInput[];
  totalWeight: number;
  duplicates: Set<string>;
  onUpdate: (id: string, patch: Partial<HoldingInput>) => void;
  onRemove: (id: string) => void;
  onAdd: () => void;
  onEqualize: () => void;
  onNormalize: () => void;
  onLoadPreset: (name: string) => void;
  onClear: () => void;
}

/**
 * The holdings editor.
 *
 * Weights are free-form on purpose: users can type percentages, decimals or
 * plain ratios and the API normalizes on submit. The running total is shown so
 * a portfolio that does not add to 100 is visible but never blocking.
 */
export function PortfolioBuilder({
  holdings,
  totalWeight,
  duplicates,
  onUpdate,
  onRemove,
  onAdd,
  onEqualize,
  onNormalize,
  onLoadPreset,
  onClear,
}: Props) {
  // Within a rounding hair of 100 counts as balanced.
  const balanced = Math.abs(totalWeight - 100) < 0.51;
  const maxWeight = Math.max(...holdings.map((h) => h.weight), 1);

  return (
    <section className="card">
      <div className="card-header">
        <h2>Holdings</h2>
        <span className="hint">{holdings.length} row{holdings.length === 1 ? "" : "s"}</span>
      </div>

      <div className="card-body">
        <label htmlFor="preset-select">Start from a preset</label>
        <select
          id="preset-select"
          value=""
          onChange={(event) => {
            if (event.target.value) onLoadPreset(event.target.value);
          }}
          style={{ marginBottom: 14 }}
        >
          <option value="">Choose a preset…</option>
          {PRESETS.map((preset) => (
            <option key={preset.name} value={preset.name}>
              {preset.name} — {preset.description}
            </option>
          ))}
        </select>

        <div className="holding-list">
          {holdings.map((holding, index) => {
            const isDuplicate =
              holding.ticker.trim().length > 0 &&
              duplicates.has(holding.ticker.trim().toUpperCase());

            return (
              <div key={holding.id}>
                <div className="holding-row">
                  <TickerInput
                    value={holding.ticker}
                    invalid={isDuplicate}
                    ariaLabel={`Ticker for holding ${index + 1}`}
                    onChange={(ticker) => onUpdate(holding.id, { ticker })}
                  />
                  <input
                    type="number"
                    className="numeric"
                    aria-label={`Weight for holding ${index + 1}`}
                    min={0}
                    step={0.5}
                    value={Number.isFinite(holding.weight) ? holding.weight : ""}
                    placeholder="0"
                    onChange={(event) =>
                      onUpdate(holding.id, {
                        weight: event.target.value === "" ? 0 : Number(event.target.value),
                      })
                    }
                  />
                  <button
                    type="button"
                    className="icon"
                    aria-label={`Remove holding ${index + 1}`}
                    title="Remove"
                    onClick={() => onRemove(holding.id)}
                  >
                    ×
                  </button>
                </div>
                {holding.weight > 0 && (
                  <div className="weight-bar" aria-hidden="true">
                    <span style={{ width: `${(holding.weight / maxWeight) * 100}%` }} />
                  </div>
                )}
                {isDuplicate && (
                  <div style={{ fontSize: 11, color: "var(--critical)", marginTop: 3 }}>
                    Duplicate ticker
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className={`weight-summary${balanced ? "" : " off"}`}>
          <span>Total weight</span>
          <strong>
            {totalWeight.toFixed(2)}
            {balanced ? " ✓" : ""}
          </strong>
        </div>

        <div className="button-row" style={{ marginTop: 12 }}>
          {/* Each handler is wrapped so React's click event is never passed
              through as a positional argument -- onAdd takes optional
              (ticker, weight) parameters, and handing it a MouseEvent as the
              ticker corrupts the row. */}
          <button type="button" onClick={() => onAdd()}>
            + Add
          </button>
          <button type="button" className="ghost" onClick={() => onEqualize()}>
            Equal weight
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => onNormalize()}
            disabled={totalWeight <= 0}
            title="Rescale existing weights proportionally to sum to 100"
          >
            Scale to 100
          </button>
          <button type="button" className="ghost" onClick={() => onClear()}>
            Clear
          </button>
        </div>

        {!balanced && totalWeight > 0 && (
          <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "10px 0 0" }}>
            Weights do not sum to 100. They will be normalized proportionally when
            analyzed, so relative sizing is what matters.
          </p>
        )}
      </div>
    </section>
  );
}
