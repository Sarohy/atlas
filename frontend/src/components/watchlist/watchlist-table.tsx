'use client';

import { useState } from 'react';

import { useWatchlist, useRemoveFromWatchlist, useSyncWatchlist } from '@/lib/hooks/use-watchlist';
import { useTickers } from '@/lib/hooks/use-tickers';
import type { WatchlistItemResponse } from '@/lib/schemas/watchlist';
import { AddWatchlistDialog } from './add-watchlist-dialog';
import { AddToPortfolioDialog } from './add-to-portfolio-dialog';

/** Number of skeleton rows shown while loading. */
const SKELETON_ROW_COUNT = 4;
/** Number of table columns — used for colSpan. */
const COLUMN_COUNT = 7;

function SkeletonRow() {
  return (
    <tr className="border-b border-[#1e2a3f]">
      {Array.from({ length: COLUMN_COUNT }, (_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 rounded bg-[#1e2a3f] animate-pulse" />
        </td>
      ))}
    </tr>
  );
}

function fmtPrice(value: number | null | undefined): string {
  if (value == null) return '—';
  return value.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

function fmtChange(value: number | null | undefined): { text: string; cls: string } {
  if (value == null) return { text: '—', cls: 'text-[#8a95a8]' };
  const sign = value >= 0 ? '+' : '';
  return {
    text: `${sign}${value.toLocaleString('en-US', { style: 'currency', currency: 'USD' })}`,
    cls: value >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]',
  };
}

function fmtPct(value: number | null | undefined): { text: string; cls: string } {
  if (value == null) return { text: '—', cls: 'text-[#8a95a8]' };
  const sign = value >= 0 ? '+' : '';
  return {
    text: `${sign}${value.toFixed(2)}%`,
    cls: value >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]',
  };
}

/**
 * Beta colour coding:
 *   β < 0    → purple (inverse)   β < 0.8  → blue (low vol)
 *   β ≤ 1.5  → white (normal)     β > 1.5  → orange (high vol)
 */
function fmtBeta(value: number | null | undefined): { text: string; cls: string } {
  if (value == null) return { text: '—', cls: 'text-[#8a95a8]' };
  let cls = 'text-[#e8edf5]';
  if (value < 0) cls = 'text-[#c084fc]';
  else if (value < 0.8) cls = 'text-[#60a5fa]';
  else if (value > 1.5) cls = 'text-[#fb923c]';
  return { text: value.toFixed(2), cls };
}

interface RowProps {
  item: WatchlistItemResponse;
  /** True when this ticker already exists in the portfolio (disables the add action). */
  inPortfolio: boolean;
  onAddToPortfolio: (item: WatchlistItemResponse) => void;
}

function WatchlistRow({ item, inPortfolio, onAddToPortfolio }: RowProps) {
  const { mutate: remove, isPending } = useRemoveFromWatchlist();
  const pct = fmtPct(item.day_change_pct);
  const chg = fmtChange(item.day_change);
  const beta = fmtBeta(item.beta);

  return (
    <tr className="border-b border-[#1e2a3f] hover:bg-[#111827] transition-colors">
      <td className="px-4 py-3 font-mono font-bold tracking-wider text-[#e8edf5]">{item.ticker}</td>
      <td className="px-4 py-3 text-[#8a95a8] text-sm">{item.company_name}</td>
      <td className="px-4 py-3 font-mono text-right text-[#e8edf5]">
        {fmtPrice(item.current_price)}
      </td>
      <td className={`px-4 py-3 font-mono text-right ${chg.cls}`}>{chg.text}</td>
      <td className={`px-4 py-3 font-mono text-right ${pct.cls}`}>{pct.text}</td>
      <td
        className={`px-4 py-3 font-mono text-right ${beta.cls}`}
        title="1-year rolling beta vs SPY"
      >
        {beta.text}
      </td>
      <td className="px-4 py-3 text-right">
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={() => remove(item.id)}
            disabled={isPending}
            className="px-3 py-1 text-xs text-[#e05c5c] border border-[#3f2d2d] rounded hover:bg-[#2a1a1a] transition-colors disabled:opacity-40"
          >
            {isPending ? '…' : 'Remove'}
          </button>
          <button
            onClick={() => onAddToPortfolio(item)}
            disabled={inPortfolio}
            title={inPortfolio ? 'Already in portfolio' : 'Add this ticker to the portfolio'}
            className="px-3 py-1 text-xs text-[#4a90d9] border border-[#2d3f5c] rounded hover:bg-[#1e2a3f] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {inPortfolio ? 'In portfolio' : 'Add to portfolio'}
          </button>
        </div>
      </td>
    </tr>
  );
}

export function WatchlistTable() {
  const { data: items, isLoading } = useWatchlist();
  const { data: portfolioTickers } = useTickers();
  const { mutate: sync, isPending: syncing } = useSyncWatchlist();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [addToPortfolioItem, setAddToPortfolioItem] = useState<WatchlistItemResponse | null>(null);

  const portfolioSymbols = new Set(
    (portfolioTickers ?? []).map((t) => t.ticker.toUpperCase()),
  );

  const lastSynced =
    items
      ?.map((i) => i.synced_at)
      .filter((t): t is string => t != null)
      .sort()
      .at(-1) ?? null;

  return (
    <>
      {/* Toolbar */}
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-xs text-[#4a5568]">
          {lastSynced
            ? `Last synced: ${new Date(lastSynced).toLocaleTimeString()}`
            : 'Market data not yet synced'}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => sync()}
            disabled={syncing || isLoading}
            className="px-3 py-1.5 text-xs font-mono text-[#4a90d9] border border-[#2d3f5c] rounded hover:bg-[#1e2a3f] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {syncing ? 'Syncing…' : '⟳ Sync Prices'}
          </button>
          <button
            onClick={() => setDialogOpen(true)}
            className="px-3 py-1.5 bg-[#4a90d9] hover:bg-[#3a7bc8] text-[#0a0e1a] font-mono font-bold text-xs rounded transition-colors"
          >
            + Add Ticker
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded border border-[#1e2a3f] overflow-hidden overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#2d3f5c] bg-[#0d1421]">
              <th className="px-4 py-3 text-left font-mono text-xs text-[#4a90d9] tracking-widest uppercase">
                Ticker
              </th>
              <th className="px-4 py-3 text-left text-xs text-[#8a95a8] tracking-wide uppercase">
                Company
              </th>
              <th className="px-4 py-3 text-right text-xs text-[#8a95a8] tracking-wide uppercase">
                Price
              </th>
              <th className="px-4 py-3 text-right text-xs text-[#8a95a8] tracking-wide uppercase">
                Day $
              </th>
              <th className="px-4 py-3 text-right text-xs text-[#8a95a8] tracking-wide uppercase">
                Day %
              </th>
              <th
                className="px-4 py-3 text-right text-xs text-[#8a95a8] tracking-wide uppercase"
                title="1-year rolling beta vs SPY benchmark"
              >
                Beta
              </th>
              <th className="px-4 py-3 text-right text-xs text-[#8a95a8] tracking-wide uppercase">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: SKELETON_ROW_COUNT }, (_, i) => <SkeletonRow key={i} />)
            ) : items && items.length > 0 ? (
              items.map((item) => (
                <WatchlistRow
                  key={item.id}
                  item={item}
                  inPortfolio={portfolioSymbols.has(item.ticker.toUpperCase())}
                  onAddToPortfolio={setAddToPortfolioItem}
                />
              ))
            ) : (
              <tr>
                <td colSpan={COLUMN_COUNT} className="px-4 py-12 text-center text-[#4a5568]">
                  No tickers on the watchlist — add one to start monitoring.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <AddWatchlistDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
      <AddToPortfolioDialog
        item={addToPortfolioItem}
        onClose={() => setAddToPortfolioItem(null)}
      />
    </>
  );
}
