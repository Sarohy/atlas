'use client';

import { useState, useCallback } from 'react';

import { useTickerSearch } from '@/lib/hooks/use-ticker-search';
import type { TickerSearchResult } from '@/lib/schemas/ticker';

interface TickerSearchProps {
  onSelect: (ticker: TickerSearchResult) => void;
  autoFocus?: boolean;
}

export function TickerSearch({ onSelect, autoFocus }: TickerSearchProps) {
  const [query, setQuery] = useState('');
  const { data: results, isFetching } = useTickerSearch(query);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
  }, []);

  return (
    <div className="relative">
      <input
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
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4a5568] text-xs">…</span>
      )}
      {results && results.length > 0 && query.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full bg-[#0d1421] border border-[#2d3f5c] rounded shadow-lg max-h-60 overflow-auto">
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
        <div className="absolute z-50 mt-1 w-full bg-[#0d1421] border border-[#2d3f5c] rounded px-3 py-2 text-[#4a5568] text-sm">
          No results for &ldquo;{query}&rdquo;
        </div>
      )}
    </div>
  );
}
