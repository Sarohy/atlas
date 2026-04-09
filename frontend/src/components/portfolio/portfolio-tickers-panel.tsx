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
import { useClusters } from '@/lib/hooks/use-clusters';
import { TickerSearch } from './ticker-search';
import type { TickerResponse, TickerSearchResult } from '@/lib/schemas/ticker';
import type { ClusterResponse } from '@/lib/schemas/cluster';

// ─── Constants ───────────────────────────────────────────────────────────────

/** Cycling accent palette matching the ATLAS design system */
const ACCENTS = ['#38bdf8', '#4ade80', '#fbbf24', '#a78bfa', '#f472b6'] as const;

// ─── Add-form schema ─────────────────────────────────────────────────────────

const addSchema = z.object({
  shares: z
    .string()
    .min(1, 'Required')
    .refine((v) => Number(v) > 0, { message: 'Must be > 0' }),
  cluster_id: z.number().nullable().optional(),
});
type AddForm = z.infer<typeof addSchema>;

// ─── Formatters ──────────────────────────────────────────────────────────────

/** Format a position value compactly: $X.XXM, $XXXK, or — if null. */
function fmtPositionValue(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${Math.round(value)}`;
}

/** Format a nullable percentage and return text + colour tone. */
function fmtChange(pct: number | null | undefined): {
  text: string;
  tone: 'green' | 'red' | 'default';
} {
  if (pct == null) return { text: '—', tone: 'default' };
  const sign = pct >= 0 ? '+' : '';
  return {
    text: `${sign}${pct.toFixed(2)}%`,
    tone: pct > 0 ? 'green' : pct < 0 ? 'red' : 'default',
  };
}

// ─── SVG micro-icons ─────────────────────────────────────────────────────────

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
      width="14"
      height="14"
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

function IconChevronDown({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

// ─── ClusterSelect ────────────────────────────────────────────────────────────
// Native <select>/<option> cannot render colour swatches, so we use a custom
// dropdown built from buttons.

interface ClusterSelectProps {
  clusters: ClusterResponse[] | undefined;
  value: number | null;
  onChange: (v: number | null) => void;
  /** Accent colour used for the floating label and border tint. */
  accentColor?: string;
}

function ClusterSelect({
  clusters,
  value,
  onChange,
  accentColor = '#4a90d9',
}: ClusterSelectProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const selected = clusters?.find((c) => c.id === value) ?? null;

  useEffect(() => {
    function onOutsideClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onOutsideClick);
    return () => document.removeEventListener('mousedown', onOutsideClick);
  }, []);

  function select(id: number | null) {
    onChange(id);
    setOpen(false);
  }

  return (
    <div ref={containerRef} className="relative flex-1">
      {/* Floating "Cluster" label */}
      <span
        className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[9px] font-mono uppercase tracking-wider pointer-events-none z-10 select-none"
        style={{ color: `${accentColor}70` }}
      >
        Cluster
      </span>

      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="w-full flex items-center gap-1.5 pl-16 pr-2.5 py-2 bg-[#0b1120] border rounded-lg font-mono text-sm focus:outline-none transition-colors"
        style={{ borderColor: `${accentColor}40` }}
      >
        {selected ? (
          <>
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: selected.color }}
            />
            <span className="flex-1 truncate text-[#e8edf5] text-left">{selected.name}</span>
          </>
        ) : (
          <span className="flex-1 text-left text-[#4a5568]">None</span>
        )}
        <IconChevronDown className="shrink-0 text-[#4a5568] ml-auto" />
      </button>

      {/* Dropdown */}
      {open && (
        <div
          role="listbox"
          className="absolute z-50 top-full left-0 right-0 mt-1 bg-[#111827] border border-[#2d3f5c] rounded-lg shadow-xl overflow-y-auto max-h-36"
        >
          <button
            type="button"
            role="option"
            aria-selected={value === null}
            onClick={() => select(null)}
            className={`w-full flex items-center gap-2 px-3 py-2 font-mono text-sm text-left transition-colors hover:bg-white/5 ${
              value === null ? 'text-[#e8edf5]' : 'text-[#4a5568]'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-[#2d3f5c] shrink-0" />
            None
          </button>

          {clusters?.map((c) => (
            <button
              key={c.id}
              type="button"
              role="option"
              aria-selected={value === c.id}
              onClick={() => select(c.id)}
              className={`w-full flex items-center gap-2 px-3 py-2 font-mono text-sm text-left transition-colors hover:bg-white/5 ${
                value === c.id ? 'text-[#e8edf5]' : 'text-[#8a95a8]'
              }`}
            >
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: c.color }} />
              {c.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── PositionCard ─────────────────────────────────────────────────────────────

function PositionCard({ position, index }: { position: TickerResponse; index: number }) {
  const [mode, setMode] = useState<'view' | 'edit' | 'confirmDelete'>('view');
  const [sharesInput, setSharesInput] = useState(String(position.shares));
  const [clusterInput, setClusterInput] = useState<number | null>(position.cluster_id ?? null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { mutate: update, isPending: saving } = useUpdateTicker();
  const { mutate: del, isPending: deleting } = useDeleteTicker();
  const { data: clusters } = useClusters();
  const accent = ACCENTS[index % ACCENTS.length];
  const change = fmtChange(position.day_change_pct);

  useEffect(() => {
    if (mode === 'edit') {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [mode]);

  function startEdit() {
    setSharesInput(String(position.shares));
    setClusterInput(position.cluster_id ?? null);
    setMode('edit');
  }

  function cancelEdit() {
    setSharesInput(String(position.shares));
    setMode('view');
  }

  function saveEdit() {
    const n = Number(sharesInput);
    if (
      !sharesInput.trim() ||
      n <= 0 ||
      (n === position.shares && clusterInput === (position.cluster_id ?? null))
    ) {
      cancelEdit();
      return;
    }
    update(
      { id: position.id, shares: sharesInput, cluster_id: clusterInput },
      {
        onSuccess: (updated) => {
          setSharesInput(String(updated.shares));
          setClusterInput(updated.cluster_id ?? null);
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

  // ── Confirm-delete ────────────────────────────────────────────────────────
  if (mode === 'confirmDelete') {
    return (
      <div className="atlas-portfolio-ticker-expanded flex items-center gap-3 rounded-xl bg-[#f87171]/5 border border-[#f87171]/20 px-4 py-3">
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
          <p className="text-[11px] text-[#8a95a8] mt-0.5">This cannot be undone</p>
        </div>
        <button
          onClick={() => del(position.id)}
          disabled={deleting}
          className="h-8 px-3 bg-[#f87171] hover:bg-[#ef4444] text-white font-mono font-bold text-xs rounded-lg transition-colors disabled:opacity-50"
        >
          {deleting ? '…' : 'Remove'}
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

  // ── Edit ──────────────────────────────────────────────────────────────────
  if (mode === 'edit') {
    return (
      <div
        className="atlas-portfolio-ticker-expanded flex items-start gap-3 rounded-xl border px-4 py-3 transition-all"
        style={{ background: `${accent}08`, borderColor: `${accent}30` }}
      >
        <div
          className="shrink-0 w-9 h-9 rounded-xl grid place-items-center font-bold text-sm mt-0.5"
          style={{ background: `${accent}18`, color: accent, border: `1px solid ${accent}30` }}
        >
          {position.ticker.slice(0, 1)}
        </div>
        <div className="flex-1 min-w-0">
          <p
            className="font-mono font-semibold text-sm leading-tight mb-0.5"
            style={{ color: accent }}
          >
            {position.ticker}
          </p>
          <p className="text-[11px] text-[#8a95a8] truncate">{position.company_name}</p>

          <div className="flex items-center gap-2 mt-2">
            {/* Shares */}
            <div className="relative flex-1">
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
                className="w-full pl-14 pr-3 py-2 bg-[#0b1120] border rounded-lg text-[#e8edf5] font-mono text-sm focus:outline-none transition-colors text-right"
                style={{ borderColor: `${accent}40` }}
              />
            </div>

            {/* Cluster with colour swatches */}
            <ClusterSelect
              clusters={clusters}
              value={clusterInput}
              onChange={setClusterInput}
              accentColor={accent}
            />

            {/* Save */}
            <button
              onClick={saveEdit}
              disabled={saving}
              aria-label="Save"
              className="w-8 h-8 flex items-center justify-center rounded-lg text-[#0a0e1a] transition-colors shrink-0"
              style={{ background: accent }}
            >
              {saving ? <span className="text-xs">…</span> : <IconCheck />}
            </button>

            {/* Cancel */}
            <button
              onClick={cancelEdit}
              aria-label="Cancel"
              className="w-8 h-8 flex items-center justify-center rounded-lg text-[#4a5568] hover:text-[#8a95a8] hover:bg-white/5 transition-colors shrink-0"
            >
              <IconX />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── View ──────────────────────────────────────────────────────────────────
  return (
    <article className="atlas-portfolio-ticker">
      <div
        className="atlas-portfolio-ticker-badge"
        style={{ background: `${accent}12`, color: accent }}
      >
        {position.ticker.slice(0, 1)}
      </div>
      <div className="atlas-portfolio-ticker-copy">
        <p className="atlas-portfolio-ticker-symbol">{position.ticker}</p>
        <p className="atlas-portfolio-ticker-label">{position.company_name ?? position.ticker}</p>
      </div>
      <div className="atlas-portfolio-ticker-metrics">
        <p className="atlas-portfolio-ticker-price">{fmtPositionValue(position.position_value)}</p>
        <p className={`atlas-portfolio-ticker-change is-${change.tone}`}>{change.text}</p>
      </div>
      <div className="atlas-portfolio-ticker-actions">
        <button
          onClick={startEdit}
          aria-label={`Edit ${position.ticker}`}
          className="atlas-portfolio-ticker-action"
        >
          <IconPencil />
        </button>
        <button
          onClick={() => setMode('confirmDelete')}
          aria-label={`Remove ${position.ticker}`}
          className="atlas-portfolio-ticker-action atlas-portfolio-ticker-action--danger"
        >
          <IconTrash />
        </button>
      </div>
    </article>
  );
}

// ─── AddPositionPanel ─────────────────────────────────────────────────────────

function AddPositionPanel({ onClose }: { onClose: () => void }) {
  const [selectedTicker, setSelectedTicker] = useState<TickerSearchResult | null>(null);
  const [clusterValue, setClusterValue] = useState<number | null>(null);
  const sharesRef = useRef<HTMLInputElement | null>(null);
  const { mutate: create, isPending } = useCreateTicker();
  const { data: clusters } = useClusters();
  const { data: existingTickers } = useTickers();

  const excludedTickers = new Set((existingTickers ?? []).map((t) => t.ticker.toUpperCase()));

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
    setClusterValue(null);
    onClose();
  }

  function onSubmit(data: AddForm) {
    if (!selectedTicker) return;
    create(
      {
        ticker: selectedTicker.ticker,
        company_name: selectedTicker.name,
        shares: data.shares,
        cluster_id: clusterValue,
      },
      {
        onSuccess: () => {
          reset();
          setSelectedTicker(null);
          setClusterValue(null);
          onClose();
        },
      },
    );
  }

  const { ref: sharesFormRef, ...sharesRest } = register('shares');

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="mt-3 mb-1 rounded-xl border border-[#4a90d9]/25 bg-[#0b1120]"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#0f1a2e] rounded-t-xl">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-md bg-[#4a90d9]/15 grid place-items-center text-[#4a90d9] shrink-0">
            <IconPlus />
          </span>
          <p className="font-mono font-bold text-xs text-[#e8edf5] uppercase tracking-widest">
            New Position
          </p>
        </div>
        <button
          type="button"
          onClick={handleCancel}
          aria-label="Close"
          className="text-[#3a4a5e] hover:text-[#8a95a8] transition-colors"
        >
          <IconX />
        </button>
      </div>

      <div className="px-4 pb-4 pt-3 space-y-3">
        {/* Ticker chip or search */}
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
              aria-label="Clear ticker"
              className="text-[#3a4a5e] hover:text-[#8a95a8] transition-colors"
            >
              <IconX />
            </button>
          </div>
        ) : (
          <TickerSearch onSelect={setSelectedTicker} autoFocus excludeTickers={excludedTickers} />
        )}

        {/* Shares + cluster + submit — only visible after a ticker is chosen */}
        {selectedTicker && (
          <div className="space-y-2">
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

            {/* Cluster select with colour swatches */}
            <ClusterSelect clusters={clusters} value={clusterValue} onChange={setClusterValue} />
          </div>
        )}

        {errors.shares && (
          <p className="text-[11px] text-[#f87171]">{errors.shares.message}</p>
        )}
      </div>
    </form>
  );
}

// ─── PortfolioTickersPanel ────────────────────────────────────────────────────

export function PortfolioTickersPanel() {
  const [addOpen, setAddOpen] = useState(false);
  const { data: positions, isLoading } = useTickers();

  return (
    <section className="atlas-portfolio-panel">
      <div className="atlas-portfolio-panel-header">
        <h2 className="atlas-portfolio-panel-title">All Tickers</h2>
        {!addOpen && (
          <button
            type="button"
            className="atlas-portfolio-link"
            onClick={() => setAddOpen(true)}
          >
            + Add Ticker
          </button>
        )}
      </div>

      {/* Inline add form — sits above the ticker list, not inside it */}
      {addOpen && <AddPositionPanel onClose={() => setAddOpen(false)} />}

      <div className="atlas-portfolio-ticker-list">
        {isLoading && (
          <p className="atlas-portfolio-ticker-label" style={{ paddingTop: '1rem' }}>
            Loading…
          </p>
        )}

        {!isLoading && (!positions || positions.length === 0) && (
          <p className="atlas-portfolio-ticker-label" style={{ paddingTop: '1rem' }}>
            No positions yet — click Add Ticker to get started.
          </p>
        )}

        {positions?.map((pos, i) => (
          <PositionCard key={pos.id} position={pos} index={i} />
        ))}
      </div>
    </section>
  );
}
