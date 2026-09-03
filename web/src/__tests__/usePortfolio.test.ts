import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { blankHolding, usePortfolio } from "../hooks/usePortfolio";

describe("blankHolding", () => {
  it("defaults to an empty row", () => {
    const holding = blankHolding();
    expect(holding.ticker).toBe("");
    expect(holding.weight).toBe(0);
    expect(holding.id).toBeTruthy();
  });

  it("issues unique ids", () => {
    const ids = new Set(Array.from({ length: 200 }, () => blankHolding().id));
    expect(ids.size).toBeGreaterThan(190);
  });

  it("coerces a non-string ticker to empty", () => {
    // Regression: `addHolding` is easy to wire straight to onClick, which
    // hands it a MouseEvent. That used to put an object in `ticker` and crash
    // every consumer calling `.trim()` on it.
    const holding = blankHolding({ type: "click" } as unknown as string);
    expect(holding.ticker).toBe("");
  });

  it("coerces a non-finite weight to zero", () => {
    expect(blankHolding("AAPL", Number.NaN as number).weight).toBe(0);
    expect(blankHolding("AAPL", "50" as unknown as number).weight).toBe(0);
  });
});

describe("usePortfolio", () => {
  beforeEach(() => localStorage.clear());

  it("starts from the first preset", () => {
    const { result } = renderHook(() => usePortfolio());
    expect(result.current.holdings.length).toBeGreaterThan(1);
    expect(result.current.totalWeight).toBeCloseTo(100, 5);
  });

  it("adds a row without arguments", () => {
    const { result } = renderHook(() => usePortfolio());
    const before = result.current.holdings.length;
    act(() => result.current.addHolding());
    expect(result.current.holdings).toHaveLength(before + 1);
    expect(result.current.holdings.at(-1)?.ticker).toBe("");
  });

  it("updates a single row without touching the others", () => {
    const { result } = renderHook(() => usePortfolio());
    const target = result.current.holdings[1]!;
    const untouched = result.current.holdings[0]!;
    act(() => result.current.updateHolding(target.id, { weight: 42 }));
    expect(result.current.holdings[1]!.weight).toBe(42);
    expect(result.current.holdings[0]!.weight).toBe(untouched.weight);
  });

  it("always leaves one row after removals", () => {
    const { result } = renderHook(() => usePortfolio());
    act(() => {
      for (const holding of [...result.current.holdings]) {
        result.current.removeHolding(holding.id);
      }
    });
    expect(result.current.holdings).toHaveLength(1);
  });

  it("splits weight evenly across named rows", () => {
    const { result } = renderHook(() => usePortfolio());
    act(() => result.current.equalize());
    expect(result.current.totalWeight).toBeCloseTo(100, 1);
    const weights = new Set(result.current.holdings.map((h) => h.weight));
    expect(weights.size).toBe(1);
  });

  it("rescales arbitrary ratios to sum to 100", () => {
    const { result } = renderHook(() => usePortfolio());
    act(() => {
      result.current.clear();
    });
    act(() => {
      result.current.updateHolding(result.current.holdings[0]!.id, {
        ticker: "AAPL",
        weight: 1,
      });
      result.current.addHolding("MSFT", 3);
    });
    act(() => result.current.normalizeToHundred());
    expect(result.current.totalWeight).toBeCloseTo(100, 1);
    expect(result.current.holdings[0]!.weight).toBeCloseTo(25, 1);
  });

  it("detects duplicate tickers case-insensitively", () => {
    const { result } = renderHook(() => usePortfolio());
    act(() => {
      result.current.clear();
    });
    act(() => {
      result.current.updateHolding(result.current.holdings[0]!.id, {
        ticker: "aapl",
        weight: 50,
      });
      result.current.addHolding("AAPL", 50);
    });
    expect(result.current.duplicates.has("AAPL")).toBe(true);
  });

  it("excludes unnamed and zero-weight rows from validHoldings", () => {
    const { result } = renderHook(() => usePortfolio());
    act(() => {
      result.current.clear();
    });
    act(() => {
      result.current.updateHolding(result.current.holdings[0]!.id, {
        ticker: "AAPL",
        weight: 50,
      });
      result.current.addHolding("", 20);
      result.current.addHolding("MSFT", 0);
    });
    expect(result.current.validHoldings).toHaveLength(1);
  });

  it("loads a preset by name", () => {
    const { result } = renderHook(() => usePortfolio());
    act(() => result.current.loadPreset("60/40"));
    expect(result.current.holdings.map((h) => h.ticker)).toEqual(["VOO", "BND"]);
  });

  it("ignores an unknown preset", () => {
    const { result } = renderHook(() => usePortfolio());
    const before = result.current.holdings.map((h) => h.ticker);
    act(() => result.current.loadPreset("does-not-exist"));
    expect(result.current.holdings.map((h) => h.ticker)).toEqual(before);
  });

  it("persists holdings across mounts", () => {
    const first = renderHook(() => usePortfolio());
    act(() => first.result.current.loadPreset("60/40"));
    first.unmount();

    const second = renderHook(() => usePortfolio());
    expect(second.result.current.holdings.map((h) => h.ticker)).toEqual(["VOO", "BND"]);
  });

  describe("input mode", () => {
    it("defaults to percent", () => {
      const { result } = renderHook(() => usePortfolio());
      expect(result.current.inputMode).toBe("percent");
    });

    it("derives each row's share of the portfolio", () => {
      const { result } = renderHook(() => usePortfolio());
      act(() => result.current.loadPreset("60/40"));
      const [voo, bnd] = result.current.holdings;
      expect(result.current.percentages.get(voo!.id)).toBeCloseTo(0.6, 6);
      expect(result.current.percentages.get(bnd!.id)).toBeCloseTo(0.4, 6);
    });

    it("derives shares from arbitrary units, not just percentages", () => {
      const { result } = renderHook(() => usePortfolio());
      act(() => result.current.clear());
      act(() => {
        result.current.updateHolding(result.current.holdings[0]!.id, {
          ticker: "AAPL",
          weight: 7500,
        });
        result.current.addHolding("BND", 2500);
      });
      const [a, b] = result.current.holdings;
      expect(result.current.percentages.get(a!.id)).toBeCloseTo(0.75, 6);
      expect(result.current.percentages.get(b!.id)).toBeCloseTo(0.25, 6);
    });

    it("converts percentages into amounts, preserving the split", () => {
      const { result } = renderHook(() => usePortfolio());
      act(() => result.current.loadPreset("60/40"));
      act(() => result.current.changeInputMode("amount", 10000));

      expect(result.current.inputMode).toBe("amount");
      expect(result.current.holdings.map((h) => h.weight)).toEqual([6000, 4000]);
      // The split the analysis sees is unchanged.
      const [voo] = result.current.holdings;
      expect(result.current.percentages.get(voo!.id)).toBeCloseTo(0.6, 6);
    });

    it("converts amounts back into percentages", () => {
      const { result } = renderHook(() => usePortfolio());
      act(() => result.current.clear());
      act(() => {
        result.current.updateHolding(result.current.holdings[0]!.id, {
          ticker: "AAPL",
          weight: 7500,
        });
        result.current.addHolding("BND", 2500);
      });
      act(() => result.current.changeInputMode("amount", 10000));
      act(() => result.current.changeInputMode("percent"));

      expect(result.current.holdings.map((h) => h.weight)).toEqual([75, 25]);
      expect(result.current.totalWeight).toBeCloseTo(100, 6);
    });

    it("is a no-op when switching to the mode already active", () => {
      const { result } = renderHook(() => usePortfolio());
      act(() => result.current.loadPreset("60/40"));
      act(() => result.current.changeInputMode("percent"));
      expect(result.current.holdings.map((h) => h.weight)).toEqual([60, 40]);
    });

    it("survives a mode switch with no weights entered", () => {
      const { result } = renderHook(() => usePortfolio());
      act(() => result.current.clear());
      act(() => result.current.changeInputMode("amount", 10000));
      expect(result.current.inputMode).toBe("amount");
      expect(result.current.holdings[0]!.weight).toBe(0);
    });

    it("persists the mode across mounts", () => {
      const first = renderHook(() => usePortfolio());
      act(() => first.result.current.changeInputMode("amount", 10000));
      first.unmount();

      const second = renderHook(() => usePortfolio());
      expect(second.result.current.inputMode).toBe("amount");
    });

    it("leaves zero-weight rows alone when converting", () => {
      const { result } = renderHook(() => usePortfolio());
      act(() => result.current.clear());
      act(() => {
        result.current.updateHolding(result.current.holdings[0]!.id, {
          ticker: "AAPL",
          weight: 100,
        });
        result.current.addHolding("MSFT", 0);
      });
      act(() => result.current.changeInputMode("amount", 5000));
      expect(result.current.holdings.map((h) => h.weight)).toEqual([5000, 0]);
    });
  });

  it("falls back to the default when stored data is corrupt", () => {
    localStorage.setItem("portfolio-analyzer:holdings:v1", "{not json");
    const { result } = renderHook(() => usePortfolio());
    expect(result.current.holdings.length).toBeGreaterThan(0);
  });

  it("drops malformed entries from stored data", () => {
    localStorage.setItem(
      "portfolio-analyzer:holdings:v1",
      JSON.stringify([{ ticker: "AAPL", weight: 60 }, { ticker: 5 }, null]),
    );
    const { result } = renderHook(() => usePortfolio());
    expect(result.current.holdings).toHaveLength(1);
    expect(result.current.holdings[0]!.ticker).toBe("AAPL");
  });
});
