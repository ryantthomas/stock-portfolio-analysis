import { fullDate } from "../lib/format";
import type { DataQuality } from "../lib/types";

interface Props {
  quality: DataQuality;
}

const PROVIDER_LABEL: Record<string, string> = {
  openbb: "OpenBB",
  yfinance: "Yahoo Finance",
  demo: "Demo data",
};

/**
 * States plainly where the numbers came from.
 *
 * The demo provider generates simulated prices so the app works offline, and
 * that must never be mistakable for real market data -- hence the explicit
 * warning rather than a quiet footnote.
 */
export function DataQualityBanner({ quality }: Props) {
  const label = PROVIDER_LABEL[quality.provider] ?? quality.provider;
  const isDemo = quality.provider === "demo";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {isDemo && (
        <div className="notice warn">
          <strong>Simulated data.</strong>
          <span>
            No live market data provider is available, so prices are randomly
            generated and stable only across runs. Figures below are for
            exploring the interface, not for making decisions. Install a live
            provider with <code>pip install -e 'api[yfinance]'</code> to analyze
            real prices.
          </span>
        </div>
      )}

      {quality.missing.length > 0 && (
        <div className="notice warn">
          <span>
            No price history for <strong>{quality.missing.join(", ")}</strong>.
            Those positions were dropped and the remaining weights rescaled to
            100%.
          </span>
        </div>
      )}

      <div
        style={{
          display: "flex",
          gap: 7,
          flexWrap: "wrap",
          alignItems: "center",
          fontSize: 11.5,
          color: "var(--text-muted)",
        }}
      >
        <span className="badge">Source: {label}</span>
        <span className="badge">
          {fullDate(quality.history_start)} → {fullDate(quality.history_end)}
        </span>
        <span className="badge">{quality.observations} trading days</span>
        <span className="badge">{quality.resolved.length} resolved</span>
      </div>
    </div>
  );
}
