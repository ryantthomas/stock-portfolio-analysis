import { useCallback, useEffect, useMemo, useState } from "react";

import type { HoldingInput } from "../lib/types";
import { PRESETS } from "../lib/presets";

const STORAGE_KEY = "portfolio-analyzer:holdings:v1";

function makeId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function blankHolding(ticker = "", weight = 0): HoldingInput {
  return { id: makeId(), ticker, weight };
}

function defaultHoldings(): HoldingInput[] {
  const preset = PRESETS[0];
  if (!preset) return [blankHolding()];
  return preset.holdings.map((h) => blankHolding(h.ticker, h.weight));
}

function loadStored(): HoldingInput[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length === 0) return null;
    // Re-issue ids rather than trusting whatever was persisted.
    return parsed
      .filter(
        (item): item is { ticker: string; weight: number } =>
          typeof item === "object" &&
          item !== null &&
          typeof (item as { ticker?: unknown }).ticker === "string" &&
          typeof (item as { weight?: unknown }).weight === "number",
      )
      .map((item) => blankHolding(item.ticker, item.weight));
  } catch {
    // A corrupt or unavailable store should never block the app from loading.
    return null;
  }
}

/**
 * Owns the holdings list: editing, weight helpers and persistence.
 *
 * Weights are kept as the user typed them (percentages, decimals, or arbitrary
 * ratios) and only normalized for display and on submit, so typing "3" into a
 * field never rewrites the other rows underneath the cursor.
 */
export function usePortfolio() {
  const [holdings, setHoldings] = useState<HoldingInput[]>(
    () => loadStored() ?? defaultHoldings(),
  );

  useEffect(() => {
    try {
      const payload = holdings.map(({ ticker, weight }) => ({ ticker, weight }));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // Private browsing or a full quota; persistence is a convenience only.
    }
  }, [holdings]);

  const totalWeight = useMemo(
    () => holdings.reduce((sum, h) => sum + (Number.isFinite(h.weight) ? h.weight : 0), 0),
    [holdings],
  );

  const validHoldings = useMemo(
    () => holdings.filter((h) => h.ticker.trim().length > 0 && h.weight > 0),
    [holdings],
  );

  const duplicates = useMemo(() => {
    const seen = new Map<string, number>();
    for (const h of holdings) {
      const key = h.ticker.trim().toUpperCase();
      if (!key) continue;
      seen.set(key, (seen.get(key) ?? 0) + 1);
    }
    return new Set([...seen.entries()].filter(([, n]) => n > 1).map(([t]) => t));
  }, [holdings]);

  const addHolding = useCallback((ticker = "", weight = 0) => {
    setHoldings((current) => [...current, blankHolding(ticker, weight)]);
  }, []);

  const updateHolding = useCallback((id: string, patch: Partial<HoldingInput>) => {
    setHoldings((current) =>
      current.map((h) => (h.id === id ? { ...h, ...patch } : h)),
    );
  }, []);

  const removeHolding = useCallback((id: string) => {
    setHoldings((current) => {
      const next = current.filter((h) => h.id !== id);
      // Always leave one row so the form never becomes an empty dead end.
      return next.length > 0 ? next : [blankHolding()];
    });
  }, []);

  /** Split 100% evenly across every row that has a ticker. */
  const equalize = useCallback(() => {
    setHoldings((current) => {
      const named = current.filter((h) => h.ticker.trim().length > 0);
      if (named.length === 0) return current;
      const share = Math.round((100 / named.length) * 100) / 100;
      return current.map((h) =>
        h.ticker.trim().length > 0 ? { ...h, weight: share } : h,
      );
    });
  }, []);

  /** Rescale existing weights proportionally so they sum to exactly 100. */
  const normalizeToHundred = useCallback(() => {
    setHoldings((current) => {
      const total = current.reduce((sum, h) => sum + (h.weight > 0 ? h.weight : 0), 0);
      if (total <= 0) return current;
      return current.map((h) => ({
        ...h,
        weight: h.weight > 0 ? Math.round((h.weight / total) * 10000) / 100 : 0,
      }));
    });
  }, []);

  const loadPreset = useCallback((name: string) => {
    const preset = PRESETS.find((p) => p.name === name);
    if (!preset) return;
    setHoldings(preset.holdings.map((h) => blankHolding(h.ticker, h.weight)));
  }, []);

  const clear = useCallback(() => setHoldings([blankHolding()]), []);

  return {
    holdings,
    totalWeight,
    validHoldings,
    duplicates,
    addHolding,
    updateHolding,
    removeHolding,
    equalize,
    normalizeToHundred,
    loadPreset,
    clear,
  };
}
