import { useEffect, useRef, useState } from "react";

import { searchTickers } from "../lib/api";
import type { SearchResult } from "../lib/types";

interface Props {
  value: string;
  onChange: (ticker: string) => void;
  invalid?: boolean;
  ariaLabel: string;
}

/**
 * Ticker field with debounced autocomplete.
 *
 * Free text is always allowed: the reference universe is a convenience, not a
 * whitelist, so a symbol it has never heard of still reaches the API and is
 * resolved by whichever live provider is configured.
 */
export function TickerInput({ value, onChange, invalid, ariaLabel }: Props) {
  const [suggestions, setSuggestions] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  // Tracks the latest query so a slow response cannot overwrite a newer one.
  const queryRef = useRef("");

  useEffect(() => {
    const query = value.trim();
    queryRef.current = query;

    if (query.length < 1) {
      setSuggestions([]);
      return;
    }

    const timer = setTimeout(() => {
      searchTickers(query)
        .then((results) => {
          if (queryRef.current !== query) return;
          setSuggestions(results);
          setHighlight(0);
        })
        .catch(() => {
          // Autocomplete is optional; typing must keep working regardless.
          setSuggestions([]);
        });
    }, 180);

    return () => clearTimeout(timer);
  }, [value]);

  // Close the dropdown when focus or a click moves elsewhere.
  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  function choose(result: SearchResult) {
    onChange(result.ticker);
    setOpen(false);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((h) => (h + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((h) => (h - 1 + suggestions.length) % suggestions.length);
    } else if (event.key === "Enter") {
      const picked = suggestions[highlight];
      if (picked) {
        event.preventDefault();
        choose(picked);
      }
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const showList = open && suggestions.length > 0;

  return (
    <div className="ticker-cell" ref={containerRef}>
      <input
        type="text"
        role="combobox"
        aria-expanded={showList}
        aria-autocomplete="list"
        aria-label={ariaLabel}
        className={invalid ? "invalid" : undefined}
        value={value}
        placeholder="Ticker"
        spellCheck={false}
        autoComplete="off"
        onChange={(event) => {
          onChange(event.target.value.toUpperCase());
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <ul className="suggestions" role="listbox">
          {suggestions.map((result, index) => (
            <li
              key={result.ticker}
              role="option"
              aria-selected={index === highlight}
              onMouseEnter={() => setHighlight(index)}
              // mousedown fires before the input's blur, so the click lands.
              onMouseDown={(event) => {
                event.preventDefault();
                choose(result);
              }}
            >
              <span className="sym">{result.ticker}</span>
              <span className="desc">
                {result.name}
                {result.asset_class ? ` · ${result.asset_class}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
