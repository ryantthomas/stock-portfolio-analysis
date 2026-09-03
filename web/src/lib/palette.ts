/**
 * Chart color.
 *
 * These are the validated default palette from the dataviz reference: eight
 * categorical slots selected as an ordered set so that every *adjacent* pair
 * clears colorblind and normal-vision separation floors in both light and dark
 * mode. Slots are assigned in fixed order and never cycled -- past eight
 * classes the data folds into "Other" instead (see `foldSeries`), because
 * beyond roughly seven bins adjacent classes stop being distinguishable.
 *
 * Dark mode is a selected set of steps for the dark surface, not an automatic
 * inversion of the light one.
 *
 * Three light-mode slots sit below 3:1 contrast against the surface, so every
 * chart using them ships visible direct labels or an accompanying table.
 */

export interface Palette {
  categorical: string[];
  /** Diverging poles for correlation: cool = negative, warm = positive. */
  divergingNegative: string;
  divergingPositive: string;
  divergingMid: string;
  benchmark: string;
  grid: string;
  axis: string;
  surface: string;
}

const LIGHT: Palette = {
  categorical: [
    "#2a78d6", // blue
    "#eb6834", // orange
    "#1baf7a", // aqua
    "#eda100", // yellow
    "#e87ba4", // magenta
    "#008300", // green
    "#4a3aa7", // violet
    "#e34948", // red
  ],
  divergingNegative: "#2a78d6",
  divergingPositive: "#e34948",
  divergingMid: "#f0efec",
  benchmark: "#8a8a84",
  grid: "#e6e6e1",
  axis: "#52514e",
  surface: "#ffffff",
};

const DARK: Palette = {
  categorical: [
    "#3987e5",
    "#d95926",
    "#199e70",
    "#c98500",
    "#d55181",
    "#008300",
    "#9085e9",
    "#e66767",
  ],
  divergingNegative: "#3987e5",
  divergingPositive: "#e66767",
  divergingMid: "#383835",
  benchmark: "#8e8e86",
  grid: "#2f2f2c",
  axis: "#c3c2b7",
  surface: "#161b23",
};

export function paletteFor(dark: boolean): Palette {
  return dark ? DARK : LIGHT;
}

/**
 * Assign a categorical color by slot index.
 *
 * The index must identify the *entity*, never its current rank, so filtering
 * or re-sorting never repaints the series that remain.
 */
export function categorical(palette: Palette, index: number): string {
  const slots = palette.categorical;
  return slots[Math.min(index, slots.length - 1)] as string;
}

/**
 * Collapse a sorted series into at most `limit` slices plus an "Other"
 * aggregate, so no chart ever needs a ninth color.
 */
export function foldSeries<T extends { label: string; weight: number }>(
  items: T[],
  limit = 7,
): { label: string; weight: number; tickers: string[] }[] {
  const sorted = [...items].sort((a, b) => b.weight - a.weight);
  if (sorted.length <= limit + 1) {
    return sorted.map((item) => ({
      label: item.label,
      weight: item.weight,
      tickers: (item as { tickers?: string[] }).tickers ?? [],
    }));
  }

  const head = sorted.slice(0, limit);
  const tail = sorted.slice(limit);
  return [
    ...head.map((item) => ({
      label: item.label,
      weight: item.weight,
      tickers: (item as { tickers?: string[] }).tickers ?? [],
    })),
    {
      label: `Other (${tail.length})`,
      weight: tail.reduce((sum, item) => sum + item.weight, 0),
      tickers: tail.flatMap((item) => (item as { tickers?: string[] }).tickers ?? []),
    },
  ];
}

/**
 * Diverging scale for the correlation heatmap: gray at zero, cool toward -1,
 * warm toward +1. A neutral midpoint is what makes "uncorrelated" read as
 * nothing rather than as a value.
 */
export function correlationColor(value: number | null, palette: Palette): string {
  if (value === null) return palette.divergingMid;
  const clamped = Math.max(-1, Math.min(1, value));
  const magnitude = Math.abs(clamped);
  if (magnitude < 0.02) return palette.divergingMid;
  const pole = clamped > 0 ? palette.divergingPositive : palette.divergingNegative;
  return mix(palette.divergingMid, pole, magnitude);
}

/** Linear blend between two hex colors, `amount` in [0, 1]. */
function mix(from: string, to: string, amount: number): string {
  const a = hexToRgb(from);
  const b = hexToRgb(to);
  if (!a || !b) return to;
  const channel = (x: number, y: number) => Math.round(x + (y - x) * amount);
  return `rgb(${channel(a[0], b[0])}, ${channel(a[1], b[1])}, ${channel(a[2], b[2])})`;
}

function hexToRgb(hex: string): [number, number, number] | null {
  const match = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(hex.trim());
  if (!match) return null;
  return [
    parseInt(match[1] as string, 16),
    parseInt(match[2] as string, 16),
    parseInt(match[3] as string, 16),
  ];
}

/**
 * Text color that stays legible on a filled heatmap cell. Strongly saturated
 * cells get light text; near-neutral ones keep the normal ink color.
 */
export function correlationTextColor(value: number | null): string {
  if (value === null) return "var(--text-subtle)";
  return Math.abs(value) > 0.55 ? "#ffffff" : "var(--text)";
}

/** Severity accent for findings. Status colors are reserved, never reused as series. */
export function severityColor(severity: string): string {
  switch (severity) {
    case "critical":
      return "var(--critical)";
    case "warning":
      return "var(--warning)";
    default:
      return "var(--info)";
  }
}

/** Diversification grade accent, A (best) through F. */
export function gradeColor(grade: string): string {
  switch (grade) {
    case "A":
      return "var(--positive)";
    case "B":
      return "var(--info)";
    case "C":
      return "var(--warning)";
    case "D":
      return "var(--warning)";
    default:
      return "var(--critical)";
  }
}
