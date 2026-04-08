'use client';

import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { useCreateTicker, useUpdateTicker } from '@/lib/hooks/use-tickers';
import { TickerSearch } from './ticker-search';
import type { TickerResponse, TickerSearchResult } from '@/lib/schemas/ticker';

/** Shares-only form schema used in step 2. */
const sharesFormSchema = z.object({
  shares: z
    .string()
    .min(1, 'Required')
    .refine((v) => Number(v) > 0, { message: 'Must be greater than 0' }),
});
type SharesForm = z.infer<typeof sharesFormSchema>;

interface AddPositionDialogProps {
  open: boolean;
  onClose: () => void;
  /** When provided the dialog runs in edit mode (shares only). */
  editTarget?: TickerResponse | null;
}

export function AddPositionDialog({ open, onClose, editTarget }: AddPositionDialogProps) {
  const [selectedTicker, setSelectedTicker] = useState<TickerSearchResult | null>(null);

  const { mutate: create, isPending: creating } = useCreateTicker();
  const { mutate: update, isPending: updating } = useUpdateTicker();
  const isPending = creating || updating;

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<SharesForm>({ resolver: zodResolver(sharesFormSchema) });

  const isEditMode = editTarget != null;

  // Pre-fill shares when opening in edit mode
  useEffect(() => {
    if (editTarget) {
      setValue('shares', String(editTarget.shares));
    }
  }, [editTarget, setValue]);

  function handleClose() {
    reset();
    setSelectedTicker(null);
    onClose();
  }

  function onSubmit(data: SharesForm) {
    if (isEditMode && editTarget) {
      update({ id: editTarget.id, shares: data.shares }, { onSuccess: handleClose });
    } else if (selectedTicker) {
      create(
        {
          ticker: selectedTicker.ticker,
          company_name: selectedTicker.name,
          shares: data.shares,
        },
        { onSuccess: handleClose },
      );
    }
  }

  if (!open) return null;

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      {/* Panel */}
      <div className="w-full max-w-md bg-[#111827] border border-[#2d3f5c] rounded shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#1e2a3f]">
          <h2 className="font-mono font-bold text-[#e8edf5] tracking-wider uppercase text-sm">
            {isEditMode ? `Edit ${editTarget?.ticker}` : 'Add Position'}
          </h2>
          <button
            onClick={handleClose}
            className="text-[#4a5568] hover:text-[#8a95a8] transition-colors text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit(onSubmit)} className="px-5 py-5 space-y-4">
          {/* Step 1 — ticker search (create mode only) */}
          {!isEditMode && (
            <div>
              <label className="block mb-1 text-xs text-[#8a95a8] uppercase tracking-wide">
                Ticker
              </label>
              {selectedTicker ? (
                <div className="flex items-center gap-2 px-3 py-2 bg-[#0d1421] border border-[#4a90d9] rounded">
                  <span className="font-mono font-bold text-[#4a90d9]">
                    {selectedTicker.ticker}
                  </span>
                  <span className="text-[#8a95a8] text-sm flex-1 truncate">
                    {selectedTicker.name}
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedTicker(null)}
                    className="text-[#4a5568] hover:text-[#8a95a8] text-xs ml-auto"
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <TickerSearch onSelect={setSelectedTicker} />
              )}
            </div>
          )}

          {/* Step 2 — shares input */}
          {(isEditMode || selectedTicker) && (
            <div>
              <label
                htmlFor="shares-input"
                className="block mb-1 text-xs text-[#8a95a8] uppercase tracking-wide"
              >
                Shares
              </label>
              <input
                id="shares-input"
                type="number"
                step="any"
                min="0.0001"
                {...register('shares')}
                className="w-full px-3 py-2 bg-[#0d1421] border border-[#2d3f5c] rounded text-[#e8edf5] font-mono text-sm focus:outline-none focus:border-[#4a90d9] transition-colors"
                placeholder="0.0000"
                autoFocus
              />
              {errors.shares && (
                <p className="mt-1 text-xs text-[#e05c5c]">{errors.shares.message}</p>
              )}
            </div>
          )}

          {/* Footer action */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={isPending || (!isEditMode && !selectedTicker)}
              className="w-full py-2 bg-[#4a90d9] hover:bg-[#3a7bc8] text-[#0a0e1a] font-mono font-bold text-sm rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isPending ? 'Saving…' : isEditMode ? 'Update Shares' : 'Add to Portfolio'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
