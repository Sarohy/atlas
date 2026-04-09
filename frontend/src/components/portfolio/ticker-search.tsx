'use client';

import { useState, useCallback, useRef, useEffect } from 'react';

import { useTickerSearch } from '@/lib/hooks/use-ticker-search';
import type { TickerSearchResult } from '@/lib/schemas/ticker';

interface TickerSearchProps {
  onSelect: (ticker: TickerSearchResult) => void;
  autoFocus?: boolean;
  /** Ticker symbols (upper-cased) that should be hidden from results. */
  excludeTickers?: Set<string>;
}

export function TickerSearch({ onSelect, autoFocus, excludeTickers }: TickerSearchProps) {
  const [query, setQuery] = useState('');
  const { data: rawResults, isFetching } = useTickerSearch(query);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});

  const results = rawResults?.filter((r) => !excludeTickers?.has(r.ticker.toUpperCase()));
  const showDropdown = query.length > 0;

  // Recompute the fixed position every time the dropdown should appear so it
  // tracks the input even if the dialog has shifted since last render.
  useEffect(() => {
    if (!showDropdown || !inputRef.current) return;
    const r = inputRef.current.getBoundingClientRect();
    setDropdownStyle({
      position: 'fixed',
      top: r.bottom + 4,
      left: r.left,
      width: r.width,
      zIndex: 9999,
    });
  }, [showDropdown, results]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
  }, []);

  return (
    <div className="relative">
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={handleChange}
        placeholder="Search ticker or company…"
        className="w-full px-3 py-2 bg-[#0d1421] border border-[#2d3f5c] rounded text-[#e8edf5] placeholder-[#4a5568] font-mono text-sm focus:outline-none focus:border-[#4a90d9] transition-colors"
        autoComplete="off"
        spellCheck={false}
        autoFocus={autoFocus}
      />
      {isFetching && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4a5568]">
          <svg
            aria-label="Searching…"
            className="w-4 h-4 animate-spin"
            fill="none"
            role="status"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2.5}
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
          </svg>
        </span>
      )}
      {results && results.length > 0 && query.length > 0 && (
        <ul
          style={dropdownStyle}
          className="bg-[#0d1421] border border-[#2d3f5c] rounded shadow-lg max-h-60 overflow-auto"
        >
          {results.map((r) => (
            <li key={r.ticker}>
              <button
                type="button"
                onClick={() => {
                  onSelect(r);
                  setQuery('');
                }}
                className="w-full px-3 py-2 flex items-center gap-3 hover:bg-[#1e2a3f] transition-colors text-left"
              >
                <span className="font-mono font-bold text-[#4a90d9] w-16 shrink-0">{r.ticker}</span>
                <span className="text-[#8a95a8] text-sm truncate">{r.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {results && results.length === 0 && query.length > 0 && !isFetching && (
        <div
          style={dropdownStyle}
          className="bg-[#0d1421] border border-[#2d3f5c] rounded px-3 py-2 text-[#4a5568] text-sm"
        >
          No results for &ldquo;{query}&rdquo;
        </div>
      )}
    </div>
  );
}
