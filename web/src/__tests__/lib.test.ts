import { describe, expect, it } from "vitest";

import { compact, number, percent, signedPercent } from "../lib/format";
import { categorical, correlationColor, foldSeries, paletteFor } from "../lib/palette";

describe("format", () => {
  it("renders a dash for missing values rather than NaN", () => {
    for (const value of [null, undefined, Number.NaN]) {
      expect(percent(value)).toBe("—");
      expect(number(value)).toBe("—");
      expect(signedPercent(value)).toBe("—");
      expect(compact(value)).toBe("—");
    }
  });

  it("formats decimals as percentages", () => {
    expect(percent(0.1234)).toBe("12.3%");
    expect(percent(0.1234, 2)).toBe("12.34%");
    expect(percent(-0.05)).toBe("-5.0%");
  });

  it("prefixes gains with a plus sign", () => {
    expect(signedPercent(0.1)).toBe("+10.0%");
    expect(signedPercent(-0.1)).toBe("-10.0%");
    // Zero is not a gain, so it takes no sign.
    expect(signedPercent(0)).toBe("0.0%");
  });

  it("abbreviates large magnitudes", () => {
    expect(compact(3.1e12)).toBe("3.1T");
    expect(compact(4.125e11)).toBe("412.5B");
    expect(compact(7.82e7)).toBe("78.2M");
    expect(compact(950)).toBe("950");
  });
});

describe("palette", () => {
  it("assigns categorical slots in fixed order", () => {
    const palette = paletteFor(false);
    expect(categorical(palette, 0)).toBe(palette.categorical[0]);
    expect(categorical(palette, 3)).toBe(palette.categorical[3]);
  });

  it("clamps past the last slot instead of cycling", () => {
    // Reusing slot 1 for a ninth series would make two different entities
    // share a color; folding to "Other" is what prevents that upstream.
    const palette = paletteFor(false);
    const last = palette.categorical.at(-1);
    expect(categorical(palette, 99)).toBe(last);
  });

  it("uses different steps for light and dark", () => {
    expect(paletteFor(false).categorical).not.toEqual(paletteFor(true).categorical);
  });

  it("leaves a short series untouched", () => {
    const items = [
      { label: "A", weight: 0.5 },
      { label: "B", weight: 0.3 },
      { label: "C", weight: 0.2 },
    ];
    expect(foldSeries(items, 7).map((s) => s.label)).toEqual(["A", "B", "C"]);
  });

  it("sorts descending by weight", () => {
    const items = [
      { label: "small", weight: 0.1 },
      { label: "big", weight: 0.6 },
      { label: "mid", weight: 0.3 },
    ];
    expect(foldSeries(items, 7).map((s) => s.label)).toEqual(["big", "mid", "small"]);
  });

  it("folds a long tail into a single Other bucket", () => {
    const items = Array.from({ length: 12 }, (_, i) => ({
      label: `S${i}`,
      weight: (12 - i) / 78,
    }));
    const folded = foldSeries(items, 7);
    expect(folded).toHaveLength(8);
    expect(folded.at(-1)?.label).toBe("Other (5)");
  });

  it("preserves total weight when folding", () => {
    const items = Array.from({ length: 10 }, (_, i) => ({ label: `S${i}`, weight: 0.1 }));
    const total = foldSeries(items, 7).reduce((sum, s) => sum + s.weight, 0);
    expect(total).toBeCloseTo(1, 6);
  });

  it("carries tickers into the Other bucket", () => {
    const items = Array.from({ length: 9 }, (_, i) => ({
      label: `S${i}`,
      weight: (9 - i) / 45,
      tickers: [`T${i}`],
    }));
    const other = foldSeries(items, 7).at(-1);
    expect(other?.tickers).toEqual(["T7", "T8"]);
  });

  it("returns the neutral midpoint for zero and missing correlation", () => {
    const palette = paletteFor(false);
    expect(correlationColor(null, palette)).toBe(palette.divergingMid);
    expect(correlationColor(0, palette)).toBe(palette.divergingMid);
  });

  it("moves toward opposite poles for positive and negative correlation", () => {
    const palette = paletteFor(false);
    expect(correlationColor(1, palette)).not.toBe(correlationColor(-1, palette));
    expect(correlationColor(0.9, palette)).toMatch(/^rgb\(/);
  });
});
