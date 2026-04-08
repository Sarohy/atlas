'use client';

import { useState } from 'react';
import { useAddToWatchlist, useWatchlist } from '@/lib/hooks/use-watchlist';
import { useTickers } from '@/lib/hooks/use-tickers';
import { TickerSearch } from '@/components/portfolio/ticker-search';
import type { TickerSearchResult } from '@/lib/schemas/ticker';

interface AddWatchlistDialogProps {
  open: boolean;
  onClose: () => void;
}

export function AddWatchlistDialog({ open, onClose }: AddWatchlistDialogProps) {
  const [selected, setSelected] = useState<TickerSearchResult | null>(null);
  const { mutate: add, isPending, error } = useAddToWatchlist();
  const { data: portfolioTickers } = useTickers();
  const { data: watchlistItems } = useWatchlist();

  const excludedTickers = new Set([
    ...(portfolioTickers ?? []).map((t) => t.ticker.toUpperCase()),
    ...(watchlistItems ?? []).map((w) => w.ticker.toUpperCase()),
  ]);

  function handleClose() {
    setSelected(null);
    onClose();
  }

  function handleAdd() {
    if (!selected) return;
    add({ ticker: selected.ticker, company_name: selected.name }, { onSuccess: handleClose });
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div className="w-full max-w-md bg-[#111827] border border-[#2d3f5c] rounded shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#1e2a3f]">
          <h2 className="font-mono font-bold text-[#e8edf5] tracking-wider uppercase text-sm">
            Add to Watchlist
          </h2>
          <button
            onClick={handleClose}
            className="text-[#4a5568] hover:text-[#8a95a8] transition-colors text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-5 space-y-4">
          <div>
            <label className="block mb-1 text-xs text-[#8a95a8] uppercase tracking-wide">
              Ticker
            </label>
            {selected ? (
              <div className="flex items-center gap-2 px-3 py-2 bg-[#0d1421] border border-[#4a90d9] rounded">
                <span className="font-mono font-bold text-[#4a90d9]">{selected.ticker}</span>
                <span className="text-[#8a95a8] text-sm flex-1 truncate">{selected.name}</span>
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="text-[#4a5568] hover:text-[#8a95a8] text-xs ml-auto"
                >
                  ✕
                </button>
              </div>
            ) : (
              <TickerSearch onSelect={setSelected} autoFocus excludeTickers={excludedTickers} />
            )}
          </div>

          {error && (
            <p className="text-xs text-[#e05c5c]">
              {error instanceof Error ? error.message : 'Failed to add ticker.'}
            </p>
          )}

          <div className="pt-1">
            <button
              onClick={handleAdd}
              disabled={!selected || isPending}
              className="w-full py-2 bg-[#4a90d9] hover:bg-[#3a7bc8] text-[#0a0e1a] font-mono font-bold text-sm rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isPending ? 'Adding…' : 'Add to Watchlist'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
