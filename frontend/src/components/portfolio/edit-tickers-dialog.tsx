'use client';

import { useState, useRef, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import {
  useTickers,
  useUpdateTicker,
  useDeleteTicker,
  useCreateTicker,
} from '@/lib/hooks/use-tickers';
import { TickerSearch } from './ticker-search';
import type { TickerResponse, TickerSearchResult } from '@/lib/schemas/ticker';

interface EditTickersDialogProps {
  open: boolean;
  onClose: () => void;
}

const addSchema = z.object({
  shares: z
    .string()
    .min(1, 'Required')
    .refine((v) => Number(v) > 0, { message: 'Must be > 0' }),
});
type AddForm = z.infer<typeof addSchema>;

/** Cycling accent palette matching the ATLAS design system */
const ACCENTS = ['#38bdf8', '#4ade80', '#fbbf24', '#a78bfa', '#f472b6'] as const;

// ─── SVG micro-icons (inline, no deps) ──────────────────────────────────────

function IconPencil({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
      <path d="m15 5 4 4" />
    </svg>
  );
}

function IconTrash({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
    </svg>
  );
}

function IconCheck({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function IconX({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}

function IconPlus({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

// ─── Position card ───────────────────────────────────────────────────────────

function PositionCard({ position, index }: { position: TickerResponse; index: number }) {
  const [mode, setMode] = useState<'view' | 'edit' | 'confirmDelete'>('view');
  const [sharesInput, setSharesInput] = useState(String(position.shares));
  const inputRef = useRef<HTMLInputElement>(null);
  const { mutate: update, isPending: saving } = useUpdateTicker();
  const { mutate: del, isPending: deleting } = useDeleteTicker();
  const accent = ACCENTS[index % ACCENTS.length];

  useEffect(() => {
    if (mode === 'edit') {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [mode]);

  function startEdit() {
    setSharesInput(String(position.shares));
    setMode('edit');
  }

  function cancelEdit() {
    setSharesInput(String(position.shares));
    setMode('view');
  }

  function saveEdit() {
    const n = Number(sharesInput);
    if (!sharesInput.trim() || n <= 0 || n === position.shares) {
      cancelEdit();
      return;
    }
    update(
      { id: position.id, shares: sharesInput },
      {
        onSuccess: (updated) => {
          setSharesInput(String(updated.shares));
          setMode('view');
        },
      },
    );
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      saveEdit();
    }
    if (e.key === 'Escape') cancelEdit();
  }

  // ── Confirm delete state ──
  if (mode === 'confirmDelete') {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[#f87171]/5 border border-[#f87171]/20 transition-all">
        <div
          className="shrink-0 w-9 h-9 rounded-xl grid place-items-center font-bold text-sm"
          style={{ background: `${accent}15`, color: accent }}
        >
          {position.ticker.slice(0, 1)}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-mono font-semibold text-sm text-[#f87171]">
            Remove {position.ticker}?
          </p>
          <p className="text-[11px] text-[#8a95a8] mt-0.5">This action cannot be undone</p>
        </div>
        <button
          onClick={() => del(position.id)}
          disabled={deleting}
          className="h-8 px-3 bg-[#f87171] hover:bg-[#ef4444] text-white font-mono font-bold text-xs rounded-lg transition-colors disabled:opacity-50"
        >
          {deleting ? 'Removing…' : 'Remove'}
        </button>
        <button
          onClick={() => setMode('view')}
          className="h-8 px-2 text-[#8a95a8] hover:text-[#e8edf5] text-xs transition-colors"
        >
          Cancel
        </button>
      </div>
    );
  }

  // ── Edit state ──
  if (mode === 'edit') {
    return (
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-xl border transition-all"
        style={{ background: `${accent}08`, borderColor: `${accent}30` }}
      >
        <div
          className="shrink-0 w-9 h-9 rounded-xl grid place-items-center font-bold text-sm"
          style={{ background: `${accent}18`, color: accent, border: `1px solid ${accent}30` }}
        >
          {position.ticker.slice(0, 1)}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-mono font-semibold text-sm leading-tight" style={{ color: accent }}>
            {position.ticker}
          </p>
          <p className="text-[11px] text-[#8a95a8] truncate mt-0.5">{position.company_name}</p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <div className="relative">
            <span
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[9px] font-mono uppercase tracking-wider pointer-events-none"
              style={{ color: `${accent}60` }}
            >
              Shares
            </span>
            <input
              ref={inputRef}
              type="number"
              step="any"
              min="0.0001"
              value={sharesInput}
              onChange={(e) => setSharesInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-32 pl-14 pr-3 py-2 bg-[#0b1120] border rounded-lg text-[#e8edf5] font-mono text-sm focus:outline-none transition-colors text-right"
              style={{ borderColor: `${accent}40` }}
            />
          </div>
          <button
            onClick={saveEdit}
            disabled={saving}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-[#0a0e1a] transition-colors"
            style={{ background: accent }}
          >
            {saving ? <span className="text-xs">…</span> : <IconCheck />}
          </button>
          <button
            onClick={cancelEdit}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-[#4a5568] hover:text-[#8a95a8] hover:bg-white/5 transition-colors"
          >
            <IconX />
          </button>
        </div>
      </div>
    );
  }

  // ── Default view state ──
  return (
    <div className="group flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/[0.02] transition-all">
      <div
        className="shrink-0 w-9 h-9 rounded-xl grid place-items-center font-bold text-sm"
        style={{ background: `${accent}12`, color: accent }}
      >
        {position.ticker.slice(0, 1)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm text-[#e8edf5] leading-tight">{position.ticker}</p>
        <p className="text-[11px] text-[#4a5568] truncate mt-0.5 group-hover:text-[#8a95a8] transition-colors">
          {position.company_name}
        </p>
      </div>
      <div className="text-right shrink-0 mr-1">
        <p className="text-sm text-[#e8edf5]">{position.shares}</p>
        <p className="text-[10px] text-[#3a4a5e] mt-0.5">shares</p>
      </div>
      {/* Action buttons — appear on hover */}
      <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={startEdit}
          aria-label={`Edit ${position.ticker}`}
          className="w-8 h-8 flex items-center justify-center rounded-lg text-[#4a90d9] hover:bg-[#4a90d9]/10 transition-colors"
        >
          <IconPencil />
        </button>
        <button
          onClick={() => setMode('confirmDelete')}
          aria-label={`Remove ${position.ticker}`}
          className="w-8 h-8 flex items-center justify-center rounded-lg text-[#3a4a5e] hover:text-[#f87171] hover:bg-[#f87171]/10 transition-colors"
        >
          <IconTrash />
        </button>
      </div>
    </div>
  );
}

// ─── Add position panel ──────────────────────────────────────────────────────

function AddPositionPanel() {
  const [open, setOpen] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<TickerSearchResult | null>(null);
  const sharesRef = useRef<HTMLInputElement | null>(null);
  const { mutate: create, isPending } = useCreateTicker();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AddForm>({ resolver: zodResolver(addSchema) });

  useEffect(() => {
    if (selectedTicker) sharesRef.current?.focus();
  }, [selectedTicker]);

  function handleCancel() {
    reset();
    setSelectedTicker(null);
    setOpen(false);
  }

  function onSubmit(data: AddForm) {
    if (!selectedTicker) return;
    create(
      { ticker: selectedTicker.ticker, company_name: selectedTicker.name, shares: data.shares },
      {
        onSuccess: () => {
          reset();
          setSelectedTicker(null);
          setOpen(false);
        },
      },
    );
  }

  const { ref: sharesFormRef, ...sharesRest } = register('shares');

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-3 w-full px-5 py-4 rounded-xl border border-dashed border-[#2d3f5c] hover:border-[#4a90d9]/40 hover:bg-[#4a90d9]/[0.03] transition-all group"
      >
        <span className="w-9 h-9 rounded-xl bg-[#4a90d9]/10 border border-[#4a90d9]/20 grid place-items-center text-[#4a90d9] shrink-0 group-hover:bg-[#4a90d9]/15 transition-colors">
          <IconPlus />
        </span>
        <div className="text-left">
          <p className="font-mono font-bold text-sm text-[#4a90d9]">Add New Position</p>
          <p className="text-[11px] text-[#3a4a5e] mt-0.5 group-hover:text-[#4a5568] transition-colors">
            Search for a ticker and set the number of shares
          </p>
        </div>
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="rounded-xl border border-[#4a90d9]/25 bg-[#0b1120]"
    >
      <div className="flex items-center justify-between px-4 py-3 bg-[#0f1a2e] rounded-t-xl">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-md bg-[#4a90d9]/15 grid place-items-center text-[#4a90d9] shrink-0">
            <IconPlus className="w-3 h-3" />
          </span>
          <p className="font-mono font-bold text-xs text-[#e8edf5] uppercase tracking-widest">
            New Position
          </p>
        </div>
        <button
          type="button"
          onClick={handleCancel}
          className="text-[#3a4a5e] hover:text-[#8a95a8] transition-colors"
        >
          <IconX />
        </button>
      </div>

      <div className="px-4 pb-4 pt-3 space-y-3">
        {/* Ticker search or chip */}
        {selectedTicker ? (
          <div className="flex items-center gap-2 px-3 py-2.5 bg-[#111827] border border-[#4a90d9]/40 rounded-lg">
            <span className="w-7 h-7 rounded-md bg-[#4a90d9]/15 grid place-items-center font-mono font-bold text-xs text-[#4a90d9] shrink-0">
              {selectedTicker.ticker.slice(0, 1)}
            </span>
            <div className="flex-1 min-w-0">
              <p className="font-mono font-bold text-sm text-[#4a90d9]">{selectedTicker.ticker}</p>
              <p className="text-[11px] text-[#8a95a8] truncate">{selectedTicker.name}</p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedTicker(null)}
              className="text-[#3a4a5e] hover:text-[#8a95a8] transition-colors"
            >
              <IconX className="w-3 h-3" />
            </button>
          </div>
        ) : (
          <TickerSearch onSelect={setSelectedTicker} autoFocus />
        )}

        {/* Shares + submit */}
        {selectedTicker && (
          <div className="flex items-center gap-2">
            <div className="flex-1 relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[10px] font-mono text-[#3a4a5e] uppercase tracking-widest pointer-events-none">
                Shares
              </span>
              <input
                type="number"
                step="any"
                min="0.0001"
                placeholder="0.0000"
                {...sharesRest}
                ref={(el) => {
                  sharesFormRef(el);
                  sharesRef.current = el;
                }}
                className="w-full pl-16 pr-3 py-2.5 bg-[#111827] border border-[#2d3f5c] rounded-lg text-[#e8edf5] font-mono text-sm focus:outline-none focus:border-[#4a90d9] transition-colors text-right"
              />
            </div>
            <button
              type="submit"
              disabled={isPending}
              className="shrink-0 h-10 px-5 bg-[#4a90d9] hover:bg-[#3a7bc8] text-[#0a0e1a] font-mono font-bold text-sm rounded-lg transition-colors disabled:opacity-40"
            >
              {isPending ? '…' : 'Add'}
            </button>
          </div>
        )}
        {errors.shares && <p className="text-[11px] text-[#f87171]">{errors.shares.message}</p>}
      </div>
    </form>
  );
}

// ─── Main dialog ─────────────────────────────────────────────────────────────

export function EditTickersDialog({ open, onClose }: EditTickersDialogProps) {
  const { data: positions, isLoading } = useTickers();
  const count = positions?.length ?? 0;

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-2xl bg-[#111827] border border-[#1e2a3f] rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 shrink-0">
          <div>
            <h2 className="font-mono font-bold text-lg text-[#e8edf5] tracking-widest uppercase">
              Manage Positions
            </h2>
            <p className="mt-1 text-xs text-[#4a5568]">
              {count > 0
                ? `${count} position${count !== 1 ? 's' : ''} in your portfolio`
                : 'Your portfolio is empty — add your first position'}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-9 h-9 flex items-center justify-center rounded-xl text-[#3a4a5e] hover:text-[#8a95a8] hover:bg-white/5 transition-colors"
          >
            <IconX />
          </button>
        </div>

        {/* ── Add new ── */}
        <div className="px-6 pb-4 shrink-0">
          <AddPositionPanel />
        </div>

        {/* ── Divider with label ── */}
        {count > 0 && (
          <div className="flex items-center gap-3 px-6 pb-2 shrink-0">
            <div className="flex-1 h-px bg-[#1e2a3f]" />
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#3a4a5e]">
              {count} holding{count !== 1 ? 's' : ''}
            </p>
            <div className="flex-1 h-px bg-[#1e2a3f]" />
          </div>
        )}

        {/* ── Position list ── */}
        <div className="overflow-y-auto flex-1 px-6 pb-6">
          {isLoading && <p className="py-8 text-center text-sm text-[#8a95a8]">Loading…</p>}

          {!isLoading && count === 0 && (
            <div className="py-10 text-center">
              <p className="text-sm text-[#4a5568]">No positions yet</p>
              <p className="text-xs text-[#2d3f5c] mt-1">Click the button above to get started</p>
            </div>
          )}

          <div className="space-y-1.5">
            {positions?.map((pos, i) => (
              <PositionCard key={pos.id} position={pos} index={i} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
