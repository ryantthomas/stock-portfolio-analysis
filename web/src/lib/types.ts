/**
 * Types mirroring the FastAPI response models in `api/app/schemas.py`.
 * Keep the two in sync -- they are the contract between the two halves.
 */

export type Severity = "info" | "warning" | "critical";

export interface HoldingInput {
  /** Stable key so React list rows survive reordering and ticker edits. */
  id: string;
  ticker: string;
  weight: number;
}

export interface HoldingDetail {
  ticker: string;
  name: string | null;
  sector: string;
  industry: string;
  country: string;
  asset_class: string;
  currency: string;
  market_cap: number | null;
  pe_ratio: number | null;
  dividend_yield: number | null;
  beta: number | null;
  weight: number;
  last_price: number | null;
  return_1y: number | null;
  annual_vol: number | null;
  contribution_to_return: number | null;
  contribution_to_risk: number | null;
  marginal_risk: number | null;
}

export interface AllocationSlice {
  label: string;
  weight: number;
  tickers: string[];
}

export interface RiskMetrics {
  annual_return: number | null;
  annual_vol: number | null;
  sharpe: number | null;
  sortino: number | null;
  max_drawdown: number | null;
  beta: number | null;
  alpha: number | null;
  tracking_error: number | null;
  var_95: number | null;
  cvar_95: number | null;
  best_day: number | null;
  worst_day: number | null;
  positive_days: number | null;
}

export interface DiversificationMetrics {
  holdings_count: number;
  hhi: number;
  effective_holdings: number;
  top_weight: number;
  top5_weight: number;
  avg_correlation: number | null;
  diversification_ratio: number | null;
  sector_count: number;
  sector_hhi: number | null;
  score: number;
  grade: string;
  components: Record<string, number>;
}

export interface Opportunity {
  id: string;
  severity: Severity;
  kind: string;
  title: string;
  detail: string;
  tickers: string[];
  metric: number | null;
}

export interface SeriesPoint {
  date: string;
  portfolio: number;
  benchmark: number | null;
}

export interface DrawdownPoint {
  date: string;
  drawdown: number;
}

export interface CorrelationMatrix {
  tickers: string[];
  matrix: (number | null)[][];
}

export interface DataQuality {
  provider: string;
  requested: string[];
  resolved: string[];
  missing: string[];
  warnings: string[];
  history_start: string | null;
  history_end: string | null;
  observations: number;
}

export interface AnalyzeResponse {
  as_of: string | null;
  benchmark: string;
  data_quality: DataQuality;
  holdings: HoldingDetail[];
  allocation: Record<string, AllocationSlice[]>;
  performance: SeriesPoint[];
  drawdown: DrawdownPoint[];
  risk: RiskMetrics;
  benchmark_risk: RiskMetrics;
  diversification: DiversificationMetrics;
  correlation: CorrelationMatrix;
  opportunities: Opportunity[];
}

export interface SearchResult {
  ticker: string;
  name: string | null;
  sector: string | null;
  asset_class: string | null;
}

export interface AnalyzeRequest {
  holdings: { ticker: string; weight: number }[];
  label?: string | null;
  benchmark: string;
  lookback_days: number;
  provider: string;
}
