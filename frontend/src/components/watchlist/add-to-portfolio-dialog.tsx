'use client';

import { useState } from 'react';
import { useCreateTicker } from '@/lib/hooks/use-tickers';
import type { WatchlistItemResponse } from '@/lib/schemas/watchlist';

interface AddToPortfolioDialogProps {
  /** Watchlist item to add to the portfolio, or null when the dialog is closed. */
  item: WatchlistItemResponse | null;
  onClose: () => void;
}

/** A portfolio ticker requires a positive share count; parse + validate the input. */
function parseShares(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === '') return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

export function AddToPortfolioDialog({ item, onClose }: AddToPortfolioDialogProps) {
  const [shares, setShares] = useState('');
  const { mutate: create, isPending, error } = useCreateTicker();

  function handleClose() {
    setShares('');
    onClose();
  }

  function handleAdd() {
    if (!item) return;
    const parsed = parseShares(shares);
    if (parsed == null) return;
    create(
      {
        ticker: item.ticker,
        company_name: item.company_name,
        shares: parsed,
        cluster_id: null,
      },
      { onSuccess: handleClose },
    );
  }

  if (!item) return null;

  const sharesValid = parseShares(shares) != null;

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
            Add to Portfolio
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
            <div className="flex items-center gap-2 px-3 py-2 bg-[#0d1421] border border-[#4a90d9] rounded">
              <span className="font-mono font-bold text-[#4a90d9]">{item.ticker}</span>
              <span className="text-[#8a95a8] text-sm flex-1 truncate">{item.company_name}</span>
            </div>
          </div>

          <div>
            <label
              htmlFor="add-portfolio-shares"
              className="block mb-1 text-xs text-[#8a95a8] uppercase tracking-wide"
            >
              Shares
            </label>
            <input
              id="add-portfolio-shares"
              type="number"
              step="any"
              min="0.0001"
              placeholder="0.0000"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              autoFocus
              className="w-full px-3 py-2 bg-[#0d1421] border border-[#2d3f5c] rounded text-[#e8edf5] font-mono text-sm text-right focus:outline-none focus:border-[#4a90d9] transition-colors"
            />
          </div>

          {error && (
            <p className="text-xs text-[#e05c5c]">
              {error instanceof Error ? error.message : 'Failed to add ticker.'}
            </p>
          )}

          <div className="pt-1">
            <button
              onClick={handleAdd}
              disabled={!sharesValid || isPending}
              className="w-full py-2 bg-[#4a90d9] hover:bg-[#3a7bc8] text-[#0a0e1a] font-mono font-bold text-sm rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isPending ? 'Adding…' : 'Add to Portfolio'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
