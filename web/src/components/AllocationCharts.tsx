import { useState } from "react";

import { usePrefersDark } from "../hooks/useTheme";
import { categorical, foldSeries, paletteFor } from "../lib/palette";
import { percent } from "../lib/format";
import type { AllocationSlice } from "../lib/types";

interface Props {
  allocation: Record<string, AllocationSlice[]>;
}

const DIMENSIONS: { key: string; label: string }[] = [
  { key: "by_sector", label: "Sector" },
  { key: "by_asset_class", label: "Asset class" },
  { key: "by_country", label: "Region" },
  { key: "by_industry", label: "Industry" },
  { key: "by_ticker", label: "Position" },
];

/**
 * Allocation as sorted, directly labeled horizontal bars.
 *
 * Bars rather than a donut: allocation buckets are frequently close in size,
 * and a ring makes near-equal slices impossible to rank by eye. Bars sort
 * cleanly, label directly, and stay readable well past the point where a pie
 * has run out of distinguishable colors.
 */
export function AllocationCharts({ allocation }: Props) {
  const [dimension, setDimension] = useState("by_sector");
  const dark = usePrefersDark();
  const palette = paletteFor(dark);

  const raw = allocation[dimension] ?? [];
  const slices = foldSeries(raw, 7);
  const max = Math.max(...slices.map((s) => s.weight), 0.01);

  return (
    <section className="card">
      <div className="card-header">
        <h2>Allocation</h2>
        <span className="hint">{slices.length} buckets</span>
      </div>

      <div className="card-body">
        <div className="tabs" role="tablist" aria-label="Allocation dimension">
          {DIMENSIONS.map((option) => (
            <button
              key={option.key}
              type="button"
              role="tab"
              aria-selected={dimension === option.key}
              onClick={() => setDimension(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="alloc-bars" style={{ marginTop: 16 }}>
          {slices.map((slice, index) => (
            <div className="alloc-row" key={slice.label}>
              <span className="alloc-label" title={slice.tickers.join(", ")}>
                {slice.label}
              </span>
              <span className="alloc-track">
                <span
                  className="alloc-fill"
                  style={{
                    width: `${(slice.weight / max) * 100}%`,
                    background: categorical(palette, index),
                  }}
                />
              </span>
              <span className="alloc-value">{percent(slice.weight, 1)}</span>
            </div>
          ))}
        </div>

        {slices.length === 0 && (
          <div className="notice info" style={{ marginTop: 14 }}>
            No allocation data for this dimension.
          </div>
        )}
      </div>
    </section>
  );
}
