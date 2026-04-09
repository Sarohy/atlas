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

// ─── Schema ──────────────────────────────────────────────────────────────────

const addSchema = z.object({
  shares: z
    .string()
    .min(1, 'Required')
    .refine((v) => Number(v) > 0, { message: 'Must be > 0' }),
});
type AddForm = z.infer<typeof addSchema>;

// ─── Formatters ──────────────────────────────────────────────────────────────

function fmtPositionValue(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${Math.round(value)}`;
}

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
}

function ClusterSelect({ clusters, value, onChange }: ClusterSelectProps) {
  const [open, setOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const selected = clusters?.find((c) => c.id === value) ?? null;

  useEffect(() => {
    function onOutsideClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    // Also close when the page scrolls (trigger rect becomes stale)
    function onScroll() {
      setOpen(false);
    }
    document.addEventListener('mousedown', onOutsideClick);
    document.addEventListener('scroll', onScroll, true);
    return () => {
      document.removeEventListener('mousedown', onOutsideClick);
      document.removeEventListener('scroll', onScroll, true);
    };
  }, []);

  function handleOpen() {
    if (triggerRef.current) {
      const r = triggerRef.current.getBoundingClientRect();
      // Render below the trigger; flip up if not enough room
      const spaceBelow = window.innerHeight - r.bottom;
      const dropHeight = Math.min(176 /* max-h-44 */, (clusters?.length ?? 0) * 44 + 44);
      const top = spaceBelow >= dropHeight ? r.bottom + 4 : r.top - dropHeight - 4;
      setDropdownStyle({
        position: 'fixed',
        top,
        left: r.left,
        width: r.width,
        zIndex: 9999,
      });
    }
    setOpen((v) => !v);
  }

  function pick(id: number | null) {
    onChange(id);
    setOpen(false);
  }

  return (
    <div ref={containerRef}>
      <p className="text-[10px] font-mono text-[#4a5568] uppercase tracking-widest mb-1.5">
        Cluster
      </p>
      <button
        ref={triggerRef}
        type="button"
        onClick={handleOpen}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="w-full flex items-center gap-2 px-3 py-2.5 bg-[#0b1120] border border-[#2d3f5c] rounded-lg font-mono text-sm focus:outline-none focus:border-[#4a90d9] transition-colors"
      >
        {selected ? (
          <>
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ background: selected.color }}
            />
            <span className="flex-1 truncate text-[#e8edf5] text-left">{selected.name}</span>
          </>
        ) : (
          <span className="flex-1 text-left text-[#4a5568]">No cluster</span>
        )}
        <IconChevronDown className="shrink-0 text-[#4a5568]" />
      </button>

      {open && (
        <div
          role="listbox"
          style={dropdownStyle}
          className="bg-[#111827] border border-[#2d3f5c] rounded-lg shadow-2xl overflow-y-auto max-h-44"
        >
          <button
            type="button"
            role="option"
            aria-selected={value === null}
            onClick={() => pick(null)}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 font-mono text-sm text-left transition-colors hover:bg-white/5 ${
              value === null ? 'text-[#e8edf5]' : 'text-[#4a5568]'
            }`}
          >
            <span className="w-2.5 h-2.5 rounded-full bg-[#2d3f5c] shrink-0" />
            No cluster
          </button>
          {clusters?.map((c) => (
            <button
              key={c.id}
              type="button"
              role="option"
              aria-selected={value === c.id}
              onClick={() => pick(c.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 font-mono text-sm text-left transition-colors hover:bg-white/5 ${
                value === c.id ? 'text-[#e8edf5]' : 'text-[#8a95a8]'
              }`}
            >
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: c.color }} />
              {c.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Dialog shell ─────────────────────────────────────────────────────────────

interface DialogProps {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
}

function Dialog({ title, subtitle, onClose, children }: DialogProps) {
  // Close on Escape key
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md bg-[#111827] border border-[#1e2a3f] rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-6 pb-5 shrink-0">
          <div>
            <h2 className="font-mono font-bold text-base text-[#e8edf5] tracking-widest uppercase">
              {title}
            </h2>
            {subtitle && <p className="mt-1 text-xs text-[#4a5568]">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 flex items-center justify-center rounded-xl text-[#3a4a5e] hover:text-[#8a95a8] hover:bg-white/5 transition-colors shrink-0 ml-4"
          >
            <IconX />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 pb-6">{children}</div>
      </div>
    </div>
  );
}

// ─── EditTickerDialog ─────────────────────────────────────────────────────────

interface EditTickerDialogProps {
  position: TickerResponse;
  accent: string;
  onClose: () => void;
}

function EditTickerDialog({ position, accent, onClose }: EditTickerDialogProps) {
  const [sharesInput, setSharesInput] = useState(String(position.shares));
  const [clusterInput, setClusterInput] = useState<number | null>(position.cluster_id ?? null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { mutate: update, isPending: saving } = useUpdateTicker();
  const { data: clusters } = useClusters();
  // Use the cluster colour assigned at dialog-open time for the header badge;
  // fall back to the cycling accent colour so unassigned tickers still look distinct.
  const initialCluster = clusters?.find((c) => c.id === (position.cluster_id ?? null)) ?? null;
  const dialogColor = initialCluster?.color ?? accent;

  useEffect(() => {
    // Slight delay so the dialog animation settles before focusing
    const id = setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 60);
    return () => clearTimeout(id);
  }, []);

  function save() {
    const n = Number(sharesInput);
    if (!sharesInput.trim() || n <= 0) return;
    // No-op if nothing actually changed
    if (n === position.shares && clusterInput === (position.cluster_id ?? null)) {
      onClose();
      return;
    }
    update(
      { id: position.id, shares: sharesInput, cluster_id: clusterInput },
      { onSuccess: onClose },
    );
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      save();
    }
    if (e.key === 'Escape') onClose();
  }

  return (
    <Dialog
      title="Edit Position"
      subtitle={`${position.ticker}${position.company_name ? ` · ${position.company_name}` : ''}`}
      onClose={onClose}
    >
      {/* Ticker badge */}
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-xl mb-5"
        style={{ background: `${dialogColor}0d`, border: `1px solid ${dialogColor}25` }}
      >
        <div
          className="w-10 h-10 rounded-xl grid place-items-center font-bold text-base shrink-0"
          style={{ background: `${dialogColor}18`, color: dialogColor }}
        >
          {position.ticker.slice(0, 1)}
        </div>
        <div>
          <p className="font-mono font-semibold text-sm" style={{ color: dialogColor }}>
            {position.ticker}
          </p>
          <p className="text-[11px] text-[#8a95a8] mt-0.5">{position.company_name}</p>
        </div>
      </div>

      {/* Shares field */}
      <div className="mb-4">
        <p className="text-[10px] font-mono text-[#4a5568] uppercase tracking-widest mb-1.5">
          Shares
        </p>
        <input
          ref={inputRef}
          type="number"
          step="any"
          min="0.0001"
          value={sharesInput}
          onChange={(e) => setSharesInput(e.target.value)}
          onKeyDown={handleKeyDown}
          className="w-full px-3 py-2.5 bg-[#0b1120] border border-[#2d3f5c] rounded-lg text-[#e8edf5] font-mono text-sm focus:outline-none focus:border-[#4a90d9] transition-colors text-right"
        />
      </div>

      {/* Cluster field */}
      <div className="mb-6">
        <ClusterSelect clusters={clusters} value={clusterInput} onChange={setClusterInput} />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving || !sharesInput.trim() || Number(sharesInput) <= 0}
          className="flex-1 flex items-center justify-center gap-2 h-10 rounded-lg font-mono font-bold text-sm text-[#0a0e1a] transition-colors disabled:opacity-40"
          style={{ background: dialogColor }}
        >
          {saving ? (
            '…'
          ) : (
            <>
              <IconCheck /> Save
            </>
          )}
        </button>
        <button
          onClick={onClose}
          className="flex-1 h-10 rounded-lg font-mono text-sm text-[#8a95a8] bg-white/5 hover:bg-white/10 transition-colors"
        >
          Cancel
        </button>
      </div>
    </Dialog>
  );
}

// ─── AddTickerDialog ──────────────────────────────────────────────────────────

interface AddTickerDialogProps {
  onClose: () => void;
}

function AddTickerDialog({ onClose }: AddTickerDialogProps) {
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

  function handleClose() {
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
    <Dialog
      title="Add Ticker"
      subtitle="Search for a ticker and set the number of shares"
      onClose={handleClose}
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {/* Ticker chip or live search */}
        <div>
          <p className="text-[10px] font-mono text-[#4a5568] uppercase tracking-widest mb-1.5">
            Ticker
          </p>
          {selectedTicker ? (
            <div className="flex items-center gap-2 px-3 py-2.5 bg-[#0b1120] border border-[#4a90d9]/40 rounded-lg">
              <span className="w-7 h-7 rounded-md bg-[#4a90d9]/15 grid place-items-center font-mono font-bold text-xs text-[#4a90d9] shrink-0">
                {selectedTicker.ticker.slice(0, 1)}
              </span>
              <div className="flex-1 min-w-0">
                <p className="font-mono font-bold text-sm text-[#4a90d9]">
                  {selectedTicker.ticker}
                </p>
                <p className="text-[11px] text-[#8a95a8] truncate">{selectedTicker.name}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedTicker(null)}
                aria-label="Clear ticker"
                className="text-[#3a4a5e] hover:text-[#8a95a8] transition-colors shrink-0"
              >
                <IconX />
              </button>
            </div>
          ) : (
            <TickerSearch onSelect={setSelectedTicker} autoFocus excludeTickers={excludedTickers} />
          )}
        </div>

        {/* Shares + cluster — only visible once a ticker is chosen */}
        {selectedTicker && (
          <>
            {/* Shares */}
            <div>
              <p className="text-[10px] font-mono text-[#4a5568] uppercase tracking-widest mb-1.5">
                Shares
              </p>
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
                className="w-full px-3 py-2.5 bg-[#0b1120] border border-[#2d3f5c] rounded-lg text-[#e8edf5] font-mono text-sm focus:outline-none focus:border-[#4a90d9] transition-colors text-right"
              />
              {errors.shares && (
                <p className="text-[11px] text-[#f87171] mt-1">{errors.shares.message}</p>
              )}
            </div>

            {/* Cluster */}
            <ClusterSelect clusters={clusters} value={clusterValue} onChange={setClusterValue} />

            {/* Submit */}
            <button
              type="submit"
              disabled={isPending}
              className="w-full flex items-center justify-center gap-2 h-10 bg-[#4a90d9] hover:bg-[#3a7bc8] text-[#0a0e1a] font-mono font-bold text-sm rounded-lg transition-colors disabled:opacity-40 mt-2"
            >
              {isPending ? (
                '…'
              ) : (
                <>
                  <IconPlus /> Add Position
                </>
              )}
            </button>
          </>
        )}
      </form>
    </Dialog>
  );
}

// ─── PositionCard ─────────────────────────────────────────────────────────────

interface PositionCardProps {
  position: TickerResponse;
  index: number;
  onEdit: (position: TickerResponse) => void;
}

function PositionCard({ position, index, onEdit }: PositionCardProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { mutate: del, isPending: deleting } = useDeleteTicker();
  const { data: clusters } = useClusters();
  const accent = ACCENTS[index % ACCENTS.length] ?? ACCENTS[0];
  const cluster = clusters?.find((c) => c.id === position.cluster_id) ?? null;
  // Use the assigned cluster's hex colour as the badge colour; fall back to the
  // cycling accent palette so unassigned tickers still look distinct.
  const badgeColor = cluster?.color ?? accent;
  const change = fmtChange(position.day_change_pct);

  if (confirmDelete) {
    return (
      <div className="atlas-portfolio-ticker-expanded flex items-center gap-3 rounded-xl bg-[#f87171]/5 border border-[#f87171]/20 px-4 py-3">
        <div
          className="shrink-0 w-9 h-9 rounded-xl grid place-items-center font-bold text-sm"
          style={{ background: `${badgeColor}15`, color: badgeColor }}
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
          onClick={() => setConfirmDelete(false)}
          className="h-8 px-2 text-[#8a95a8] hover:text-[#e8edf5] text-xs transition-colors"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <article className="atlas-portfolio-ticker">
      {/* Badge — cluster colour when assigned; hover shows cluster name tooltip */}
      <div className="relative group/badge shrink-0">
        <div
          className="atlas-portfolio-ticker-badge"
          style={{ background: `${badgeColor}20`, color: badgeColor }}
        >
          {position.ticker.slice(0, 1)}
        </div>
        {cluster && (
          <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded bg-[#1e2a3f] border border-[#2d3f5c] text-[10px] font-mono text-[#e8edf5] whitespace-nowrap opacity-0 group-hover/badge:opacity-100 transition-opacity z-20 flex items-center gap-1.5">
            <span
              className="w-1.5 h-1.5 rounded-full shrink-0"
              style={{ background: cluster.color }}
            />
            {cluster.name}
          </div>
        )}
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
          onClick={() => onEdit(position)}
          aria-label={`Edit ${position.ticker}`}
          className="atlas-portfolio-ticker-action"
        >
          <IconPencil />
        </button>
        <button
          onClick={() => setConfirmDelete(true)}
          aria-label={`Remove ${position.ticker}`}
          className="atlas-portfolio-ticker-action atlas-portfolio-ticker-action--danger"
        >
          <IconTrash />
        </button>
      </div>
    </article>
  );
}

// ─── PortfolioTickersPanel ────────────────────────────────────────────────────

export function PortfolioTickersPanel() {
  const [addOpen, setAddOpen] = useState(false);
  const [editPosition, setEditPosition] = useState<TickerResponse | null>(null);
  const { data: positions, isLoading } = useTickers();

  const editIndex = editPosition ? (positions?.findIndex((p) => p.id === editPosition.id) ?? 0) : 0;
  const editAccent = ACCENTS[editIndex % ACCENTS.length] ?? ACCENTS[0];

  return (
    <>
      <section className="atlas-portfolio-panel">
        <div className="atlas-portfolio-panel-header">
          <h2 className="atlas-portfolio-panel-title">All Tickers</h2>
          <button type="button" className="atlas-portfolio-link" onClick={() => setAddOpen(true)}>
            + Add Ticker
          </button>
        </div>

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
            <PositionCard key={pos.id} position={pos} index={i} onEdit={setEditPosition} />
          ))}
        </div>
      </section>

      {addOpen && <AddTickerDialog onClose={() => setAddOpen(false)} />}

      {editPosition && (
        <EditTickerDialog
          position={editPosition}
          accent={editAccent}
          onClose={() => setEditPosition(null)}
        />
      )}
    </>
  );
}
