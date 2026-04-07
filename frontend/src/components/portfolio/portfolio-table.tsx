'use client';

import { useState } from 'react';

import { useTickers, useDeleteTicker, useSyncTickers } from '@/lib/hooks/use-tickers';
import type { TickerResponse } from '@/lib/schemas/ticker';
import { AddPositionDialog } from './add-position-dialog';

/** Number of skeleton rows to show while loading. */
const SKELETON_ROW_COUNT = 5;

/** Number of columns in the table (used for colspan). */
const COLUMN_COUNT = 9;

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

/** Format a number as USD price, e.g. $152.34 */
function fmtPrice(value: number | null | undefined): string {
  if (value == null) return '—';
  return value.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

/** Format a change-percent value with sign and colour class. */
function fmtPct(value: number | null | undefined): { text: string; cls: string } {
  if (value == null) return { text: '—', cls: 'text-[#8a95a8]' };
  const sign = value >= 0 ? '+' : '';
  return {
    text: `${sign}${value.toFixed(2)}%`,
    cls: value >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]',
  };
}

/** Format a dollar change with sign and colour class. */
function fmtChange(value: number | null | undefined): { text: string; cls: string } {
  if (value == null) return { text: '—', cls: 'text-[#8a95a8]' };
  const sign = value >= 0 ? '+' : '';
  return {
    text: `${sign}${value.toLocaleString('en-US', { style: 'currency', currency: 'USD' })}`,
    cls: value >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]',
  };
}

/**
 * Format beta with a colour hint:
 *   β > 1.5  → orange (high vol)   | β 0.8–1.5 → white (normal)
 *   β < 0.8  → blue  (low vol)    | β < 0    → purple (inverse)
 */
function fmtBeta(value: number | null | undefined): { text: string; cls: string } {
  if (value == null) return { text: '—', cls: 'text-[#8a95a8]' };
  const text = value.toFixed(2);
  let cls = 'text-[#e8edf5]';
  if (value < 0) cls = 'text-[#c084fc]';
  else if (value < 0.8) cls = 'text-[#60a5fa]';
  else if (value > 1.5) cls = 'text-[#fb923c]';
  return { text, cls };
}

interface RowProps {
  position: TickerResponse;
  onEdit: (position: TickerResponse) => void;
}

function PositionRow({ position, onEdit }: RowProps) {
  const { mutate: deletePosition, isPending } = useDeleteTicker();
  const pct = fmtPct(position.day_change_pct);
  const chg = fmtChange(position.day_change);
  const betaFmt = fmtBeta(position.beta);

  return (
    <tr className="border-b border-[#1e2a3f] hover:bg-[#111827] transition-colors">
      <td className="px-4 py-3 font-mono font-bold tracking-wider text-[#e8edf5]">
        {position.ticker}
      </td>
      <td className="px-4 py-3 text-[#8a95a8] text-sm">{position.company_name}</td>
      <td className="px-4 py-3 font-mono text-right text-[#e8edf5]">
        {Number(position.shares).toLocaleString('en-US', {
          minimumFractionDigits: 4,
          maximumFractionDigits: 4,
        })}
      </td>
      <td className="px-4 py-3 font-mono text-right text-[#e8edf5]">
        {fmtPrice(position.current_price)}
      </td>
      <td className={`px-4 py-3 font-mono text-right ${chg.cls}`}>{chg.text}</td>
      <td className={`px-4 py-3 font-mono text-right ${pct.cls}`}>{pct.text}</td>
      <td className="px-4 py-3 font-mono text-right text-[#e8edf5]">
        {fmtPrice(position.position_value)}
      </td>
      <td
        className={`px-4 py-3 font-mono text-right ${betaFmt.cls}`}
        title="1-year rolling beta vs SPY"
      >
        {betaFmt.text}
      </td>
      <td className="px-4 py-3 text-right">
        <button
          onClick={() => onEdit(position)}
          className="mr-2 px-3 py-1 text-xs text-[#4a90d9] border border-[#2d3f5c] rounded hover:bg-[#1e2a3f] transition-colors"
        >
          Edit
        </button>
        <button
          onClick={() => deletePosition(position.id)}
          disabled={isPending}
          className="px-3 py-1 text-xs text-[#e05c5c] border border-[#3f2d2d] rounded hover:bg-[#2a1a1a] transition-colors disabled:opacity-40"
        >
          {isPending ? '…' : 'Delete'}
        </button>
      </td>
    </tr>
  );
}

export function PortfolioTable() {
  const { data: positions, isLoading } = useTickers();
  const { mutate: sync, isPending: isSyncing, error: syncError } = useSyncTickers();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<TickerResponse | null>(null);

  function openEdit(position: TickerResponse) {
    setEditTarget(position);
    setDialogOpen(true);
  }

  function closeDialog() {
    setEditTarget(null);
    setDialogOpen(false);
  }

  /** Derive the last-synced timestamp from the most-recently synced position. */
  const lastSynced =
    positions
      ?.map((p) => p.synced_at)
      .filter((t): t is string => t != null)
      .sort()
      .at(-1) ?? null;

  return (
    <>
      {/* Table toolbar */}
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs text-[#4a5568]">
          {lastSynced
            ? `Last synced: ${new Date(lastSynced).toLocaleTimeString()}`
            : 'Market data not yet synced'}
        </span>
        <button
          onClick={() => sync()}
          disabled={isSyncing || isLoading}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-mono font-bold bg-[#1e2a3f] border border-[#2d3f5c] text-[#4a90d9] rounded hover:bg-[#253450] transition-colors disabled:opacity-40"
        >
          <svg
            className={`w-3 h-3 ${isSyncing ? 'animate-spin' : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          {isSyncing ? 'Syncing…' : 'Sync Prices'}
        </button>
      </div>

      {syncError && (
        <p className="mb-2 text-xs text-[#f87171]">
          Sync failed: {syncError instanceof Error ? syncError.message : 'Unknown error'}
        </p>
      )}

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
                Shares
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
              <th className="px-4 py-3 text-right text-xs text-[#8a95a8] tracking-wide uppercase">
                Value
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
            ) : positions && positions.length > 0 ? (
              positions.map((p) => <PositionRow key={p.id} position={p} onEdit={openEdit} />)
            ) : (
              <tr>
                <td colSpan={COLUMN_COUNT} className="px-4 py-12 text-center text-[#4a5568]">
                  No positions — add one to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <AddPositionDialog open={dialogOpen} onClose={closeDialog} editTarget={editTarget} />
    </>
  );
}
