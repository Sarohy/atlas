'use client';

import { useState } from 'react';

import { usePositions, useDeletePosition } from '@/lib/hooks/use-positions';
import type { PositionResponse } from '@/lib/schemas/position';
import { AddPositionDialog } from './add-position-dialog';

/** Number of skeleton rows to show while loading. */
const SKELETON_ROW_COUNT = 5;

function SkeletonRow() {
  return (
    <tr className="border-b border-[#1e2a3f]">
      {[1, 2, 3, 4].map((col) => (
        <td key={col} className="px-4 py-3">
          <div className="h-4 rounded bg-[#1e2a3f] animate-pulse" />
        </td>
      ))}
    </tr>
  );
}

interface RowProps {
  position: PositionResponse;
  onEdit: (position: PositionResponse) => void;
}

function PositionRow({ position, onEdit }: RowProps) {
  const { mutate: deletePosition, isPending } = useDeletePosition();

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
  const { data: positions, isLoading } = usePositions();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<PositionResponse | null>(null);

  function openEdit(position: PositionResponse) {
    setEditTarget(position);
    setDialogOpen(true);
  }

  function closeDialog() {
    setEditTarget(null);
    setDialogOpen(false);
  }

  return (
    <>
      <div className="rounded border border-[#1e2a3f] overflow-hidden">
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
                <td colSpan={4} className="px-4 py-12 text-center text-[#4a5568]">
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
