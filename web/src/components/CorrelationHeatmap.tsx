import { usePrefersDark } from "../hooks/useTheme";
import { correlationColor, correlationTextColor, paletteFor } from "../lib/palette";
import type { CorrelationMatrix } from "../lib/types";

interface Props {
  correlation: CorrelationMatrix;
}

/**
 * Pairwise correlation grid.
 *
 * Diverging scale with a neutral midpoint: gray at zero so "uncorrelated"
 * reads as nothing, warm toward +1 and cool toward -1. Every cell also carries
 * its numeric value, so the reading never depends on color alone.
 *
 * Red blocks are the finding worth acting on -- two holdings that move
 * together are one position wearing two tickers.
 */
export function CorrelationHeatmap({ correlation }: Props) {
  const dark = usePrefersDark();
  const palette = paletteFor(dark);
  const { tickers, matrix } = correlation;

  if (tickers.length < 2) {
    return (
      <section className="card">
        <div className="card-header">
          <h2>Correlation</h2>
        </div>
        <div className="card-body">
          <div className="notice info">
            Correlation needs at least two positions with overlapping price history.
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2>Correlation</h2>
        <span className="hint">Daily returns over the analysis window</span>
      </div>

      <div className="card-body">
        <div className="table-scroll">
          <table className="heatmap">
            <caption className="sr-only">
              Pairwise correlation of daily returns between portfolio holdings.
            </caption>
            <thead>
              <tr>
                <th scope="col" />
                {tickers.map((ticker) => (
                  <th scope="col" key={ticker}>
                    {ticker}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tickers.map((rowTicker, rowIndex) => (
                <tr key={rowTicker}>
                  <th scope="row">{rowTicker}</th>
                  {tickers.map((colTicker, colIndex) => {
                    const value = matrix[rowIndex]?.[colIndex] ?? null;
                    const isDiagonal = rowIndex === colIndex;
                    return (
                      <td key={colTicker}>
                        <div
                          className="cell"
                          style={{
                            background: isDiagonal
                              ? "var(--surface-3)"
                              : correlationColor(value, palette),
                            color: isDiagonal
                              ? "var(--text-subtle)"
                              : correlationTextColor(value),
                          }}
                          title={`${rowTicker} vs ${colTicker}: ${
                            value === null ? "not available" : value.toFixed(3)
                          }`}
                        >
                          {value === null ? "—" : value.toFixed(2)}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="heatmap-legend">
          <span>−1 moves opposite</span>
          <span
            className="scale"
            style={{
              background: `linear-gradient(to right, ${palette.divergingNegative}, ${palette.divergingMid}, ${palette.divergingPositive})`,
            }}
            aria-hidden="true"
          />
          <span>+1 moves together</span>
        </div>

        <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "10px 0 0" }}>
          Pairs above 0.85 behave almost identically. Holding both adds position
          count without adding diversification.
        </p>
      </div>
    </section>
  );
}
