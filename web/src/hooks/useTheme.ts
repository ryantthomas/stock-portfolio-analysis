import { useEffect, useState } from "react";

/**
 * Tracks the OS color scheme.
 *
 * Recharts needs real color strings rather than CSS custom properties, so the
 * chart palette has to be selected in JavaScript instead of swapped in CSS.
 */
export function usePrefersDark(): boolean {
  const [dark, setDark] = useState(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent) => setDark(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return dark;
}
