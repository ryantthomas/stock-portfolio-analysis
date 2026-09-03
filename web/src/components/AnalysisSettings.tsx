interface Props {
  benchmark: string;
  lookbackDays: number;
  provider: string;
  label: string;
  disabled: boolean;
  loading: boolean;
  onBenchmarkChange: (value: string) => void;
  onLookbackChange: (value: number) => void;
  onProviderChange: (value: string) => void;
  onLabelChange: (value: string) => void;
  onAnalyze: () => void;
}

const BENCHMARKS = [
  { value: "SPY", label: "S&P 500 (SPY)" },
  { value: "VTI", label: "US total market (VTI)" },
  { value: "QQQ", label: "Nasdaq 100 (QQQ)" },
  { value: "VT", label: "Global equity (VT)" },
  { value: "AGG", label: "US aggregate bonds (AGG)" },
];

const WINDOWS = [
  { value: 365, label: "1 year" },
  { value: 730, label: "2 years" },
  { value: 1095, label: "3 years" },
  { value: 1825, label: "5 years" },
  { value: 3650, label: "10 years" },
];

const PROVIDERS = [
  { value: "auto", label: "Auto (best available)" },
  { value: "openbb", label: "OpenBB" },
  { value: "yfinance", label: "Yahoo Finance" },
  { value: "demo", label: "Demo (offline, simulated)" },
];

export function AnalysisSettings({
  benchmark,
  lookbackDays,
  provider,
  label,
  disabled,
  loading,
  onBenchmarkChange,
  onLookbackChange,
  onProviderChange,
  onLabelChange,
  onAnalyze,
}: Props) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>Settings</h2>
      </div>
      <div className="card-body">
        <div className="field-row">
          <div>
            <label htmlFor="benchmark">Benchmark</label>
            <select
              id="benchmark"
              value={benchmark}
              onChange={(event) => onBenchmarkChange(event.target.value)}
            >
              {BENCHMARKS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="lookback">History</label>
            <select
              id="lookback"
              value={lookbackDays}
              onChange={(event) => onLookbackChange(Number(event.target.value))}
            >
              {WINDOWS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="field-row" style={{ marginTop: 12 }}>
          <div>
            <label htmlFor="provider">Data source</label>
            <select
              id="provider"
              value={provider}
              onChange={(event) => onProviderChange(event.target.value)}
            >
              {PROVIDERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="label">Name (optional)</label>
            <input
              id="label"
              type="text"
              value={label}
              placeholder="My portfolio"
              maxLength={120}
              onChange={(event) => onLabelChange(event.target.value)}
            />
          </div>
        </div>

        <button
          type="button"
          className="primary"
          style={{ marginTop: 16 }}
          disabled={disabled || loading}
          onClick={onAnalyze}
        >
          {loading ? "Analyzing…" : "Analyze portfolio"}
        </button>
      </div>
    </section>
  );
}
