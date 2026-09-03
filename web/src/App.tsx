import { useCallback, useEffect, useState } from "react";

import { AllocationCharts } from "./components/AllocationCharts";
import { AnalysisSettings } from "./components/AnalysisSettings";
import { CorrelationHeatmap } from "./components/CorrelationHeatmap";
import { DataQualityBanner } from "./components/DataQualityBanner";
import { DiversificationScore } from "./components/DiversificationScore";
import { HoldingsTable } from "./components/HoldingsTable";
import { Opportunities } from "./components/Opportunities";
import { PerformanceChart } from "./components/PerformanceChart";
import { PortfolioBuilder } from "./components/PortfolioBuilder";
import { RiskContribution } from "./components/RiskContribution";
import { RiskMetrics } from "./components/RiskMetrics";
import { usePortfolio } from "./hooks/usePortfolio";
import { ApiError, analyzePortfolio } from "./lib/api";
import type { AnalyzeResponse } from "./lib/types";

export function App() {
  const portfolio = usePortfolio();

  const [benchmark, setBenchmark] = useState("SPY");
  const [lookbackDays, setLookbackDays] = useState(1095);
  const [provider, setProvider] = useState("auto");
  const [label, setLabel] = useState("");

  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Only the first analysis auto-runs; after that the user drives it.
  const [hasRun, setHasRun] = useState(false);

  const canAnalyze =
    portfolio.validHoldings.length > 0 && portfolio.duplicates.size === 0;

  const runAnalysis = useCallback(async () => {
    if (!canAnalyze) return;

    setLoading(true);
    setError(null);
    try {
      const response = await analyzePortfolio({
        holdings: portfolio.validHoldings.map((h) => ({
          ticker: h.ticker.trim().toUpperCase(),
          weight: h.weight,
        })),
        label: label.trim() || null,
        benchmark,
        lookback_days: lookbackDays,
        provider,
      });
      setResult(response);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Something went wrong running the analysis.",
      );
      setResult(null);
    } finally {
      setLoading(false);
      setHasRun(true);
    }
  }, [canAnalyze, portfolio.validHoldings, label, benchmark, lookbackDays, provider]);

  // Analyze the default portfolio once on load so the app opens with content
  // rather than an empty panel.
  useEffect(() => {
    if (!hasRun && canAnalyze) void runAnalysis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasRun, canAnalyze]);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Portfolio Analyzer</h1>
          <div className="tagline">
            Enter tickers and weights. See concentration, correlation and risk.
          </div>
        </div>
        {result?.as_of && (
          <span className="badge">Data through {result.as_of}</span>
        )}
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <PortfolioBuilder
            holdings={portfolio.holdings}
            totalWeight={portfolio.totalWeight}
            duplicates={portfolio.duplicates}
            onUpdate={portfolio.updateHolding}
            onRemove={portfolio.removeHolding}
            onAdd={portfolio.addHolding}
            onEqualize={portfolio.equalize}
            onNormalize={portfolio.normalizeToHundred}
            onLoadPreset={portfolio.loadPreset}
            onClear={portfolio.clear}
          />

          <AnalysisSettings
            benchmark={benchmark}
            lookbackDays={lookbackDays}
            provider={provider}
            label={label}
            disabled={!canAnalyze}
            loading={loading}
            onBenchmarkChange={setBenchmark}
            onLookbackChange={setLookbackDays}
            onProviderChange={setProvider}
            onLabelChange={setLabel}
            onAnalyze={() => void runAnalysis()}
          />

          {portfolio.duplicates.size > 0 && (
            <div className="notice error">
              Remove duplicate tickers before analyzing:{" "}
              {[...portfolio.duplicates].join(", ")}
            </div>
          )}
        </aside>

        <main className="results">
          {error && (
            <div className="notice error">
              <strong>Analysis failed.</strong>
              <span>{error}</span>
            </div>
          )}

          {loading && !result && <LoadingState />}

          {!loading && !result && !error && (
            <div className="card">
              <div className="empty-state">
                <h2>Build a portfolio to get started</h2>
                <p>
                  Add tickers and assign each a weight, or load one of the
                  presets. Weights do not need to sum to 100 — they are
                  normalized for you.
                </p>
              </div>
            </div>
          )}

          {result && (
            <>
              <DataQualityBanner quality={result.data_quality} />
              <DiversificationScore metrics={result.diversification} />
              <Opportunities opportunities={result.opportunities} />
              <PerformanceChart
                performance={result.performance}
                drawdown={result.drawdown}
                benchmark={result.benchmark}
              />
              <RiskMetrics
                risk={result.risk}
                benchmarkRisk={result.benchmark_risk}
                benchmark={result.benchmark}
              />
              <AllocationCharts allocation={result.allocation} />
              <RiskContribution holdings={result.holdings} />
              <CorrelationHeatmap correlation={result.correlation} />
              <HoldingsTable holdings={result.holdings} />

              {result.data_quality.warnings.length > 0 && (
                <details className="card">
                  <summary
                    style={{
                      padding: "12px 16px",
                      cursor: "pointer",
                      fontSize: 12.5,
                      color: "var(--text-muted)",
                    }}
                  >
                    Data notes ({result.data_quality.warnings.length})
                  </summary>
                  <div className="card-body" style={{ paddingTop: 0 }}>
                    <ul
                      style={{
                        margin: 0,
                        paddingLeft: 18,
                        fontSize: 12,
                        color: "var(--text-muted)",
                      }}
                    >
                      {result.data_quality.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                </details>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <>
      <div className="skeleton" style={{ height: 168 }} />
      <div className="skeleton" style={{ height: 210 }} />
      <div className="skeleton" style={{ height: 340 }} />
    </>
  );
}
