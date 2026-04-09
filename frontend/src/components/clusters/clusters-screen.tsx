'use client';

import { useState, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import {
  useClusters,
  useCreateCluster,
  useUpdateCluster,
  useDeleteCluster,
} from '@/lib/hooks/use-clusters';
import {
  clusterCreateSchema,
  type ClusterCreate,
  type ClusterResponse,
} from '@/lib/schemas/cluster';
import type { ClustersScreenData } from '@/lib/api/clusters-shell';

// ─── Pre-set palette swatches ─────────────────────────────────────────────────

/** 12 suggested colours matching the ATLAS dark-blue design system. */
const PALETTE = [
  '#4a90d9',
  '#38bdf8',
  '#4ade80',
  '#fbbf24',
  '#f472b6',
  '#a78bfa',
  '#fb923c',
  '#f87171',
  '#2dd4bf',
  '#e879f9',
  '#818cf8',
  '#34d399',
] as const;

// ─── SVG icons ────────────────────────────────────────────────────────────────

function IconPencil({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="13"
      height="13"
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
      width="13"
      height="13"
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
      width="13"
      height="13"
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
      width="13"
      height="13"
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

// ─── Colour picker ────────────────────────────────────────────────────────────

function ColorPicker({ value, onChange }: { value: string; onChange: (c: string) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {PALETTE.map((c) => (
        <button
          key={c}
          type="button"
          aria-label={`Select colour ${c}`}
          onClick={() => onChange(c)}
          className="w-6 h-6 rounded-full transition-transform hover:scale-110 shrink-0"
          style={{
            background: c,
            outline: value === c ? `2px solid white` : '2px solid transparent',
            outlineOffset: '2px',
          }}
        />
      ))}
      {/* Custom hex input */}
      <label className="flex items-center gap-1.5 cursor-pointer">
        <span
          className="w-6 h-6 rounded-full border border-dashed border-[#4a5568] shrink-0 grid place-items-center overflow-hidden"
          style={{ background: value }}
          onClick={() => inputRef.current?.click()}
        >
          <span className="text-[8px] text-white/60">+</span>
        </span>
        <input
          ref={inputRef}
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="sr-only"
          aria-label="Custom colour"
        />
      </label>
    </div>
  );
}

// ─── Create cluster form ──────────────────────────────────────────────────────

function CreateClusterForm() {
  const [color, setColor] = useState('#4a90d9');
  const { mutate: create, isPending, isError, error } = useCreateCluster();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ClusterCreate>({
    resolver: zodResolver(clusterCreateSchema),
    defaultValues: { color: '#4a90d9' },
  });

  function onSubmit(data: ClusterCreate) {
    create(
      { ...data, color },
      {
        onSuccess: () => {
          reset();
          setColor('#4a90d9');
        },
      },
    );
  }

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="rounded-xl border border-[#1e2a3f] bg-[#0d1421] p-5 space-y-4"
      aria-label="Create cluster form"
    >
      <h2 className="font-mono font-bold text-xs text-[#e8edf5] uppercase tracking-widest">
        New Cluster
      </h2>

      <div>
        <label className="block mb-1.5 text-[10px] text-[#8a95a8] uppercase tracking-widest">
          Name
        </label>
        <input
          {...register('name')}
          placeholder="e.g. AI Core, Energy…"
          className="w-full px-3 py-2 bg-[#111827] border border-[#2d3f5c] rounded-lg text-[#e8edf5] font-mono text-sm focus:outline-none focus:border-[#4a90d9] transition-colors"
          aria-label="Cluster name"
        />
        {errors.name && <p className="mt-1 text-[11px] text-[#f87171]">{errors.name.message}</p>}
      </div>

      <div>
        <label className="block mb-2 text-[10px] text-[#8a95a8] uppercase tracking-widest">
          Colour
        </label>
        <ColorPicker value={color} onChange={setColor} />
      </div>

      {isError && (
        <p className="text-[11px] text-[#f87171]">
          {error instanceof Error ? error.message : 'Failed to create cluster.'}
        </p>
      )}

      <button
        type="submit"
        disabled={isPending}
        className="w-full py-2 bg-[#4a90d9] hover:bg-[#3a7bc8] text-[#0a0e1a] font-mono font-bold text-sm rounded-lg transition-colors disabled:opacity-40"
      >
        {isPending ? 'Creating…' : 'Create Cluster'}
      </button>
    </form>
  );
}

// ─── Edit cluster inline ──────────────────────────────────────────────────────

function EditClusterRow({ cluster, onCancel }: { cluster: ClusterResponse; onCancel: () => void }) {
  const [color, setColor] = useState(cluster.color);
  const { mutate: update, isPending } = useUpdateCluster();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ClusterCreate>({
    resolver: zodResolver(clusterCreateSchema),
    defaultValues: { name: cluster.name, color: cluster.color },
  });

  function onSubmit(data: ClusterCreate) {
    update({ id: cluster.id, data: { name: data.name, color } }, { onSuccess: onCancel });
  }

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="rounded-xl border border-[#4a90d9]/30 bg-[#0d1421] p-4 space-y-3"
    >
      <div className="flex items-center gap-3">
        <span
          className="w-3 h-3 rounded-full shrink-0"
          style={{ background: color }}
          aria-hidden="true"
        />
        <input
          {...register('name')}
          className="flex-1 px-3 py-1.5 bg-[#111827] border border-[#2d3f5c] rounded-lg text-[#e8edf5] font-mono text-sm focus:outline-none focus:border-[#4a90d9] transition-colors"
          aria-label="Edit cluster name"
        />
        <button
          type="submit"
          disabled={isPending}
          className="w-7 h-7 rounded-lg bg-[#4a90d9] text-[#0a0e1a] flex items-center justify-center"
        >
          {isPending ? <span className="text-xs">…</span> : <IconCheck />}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="w-7 h-7 rounded-lg text-[#4a5568] hover:text-[#8a95a8] flex items-center justify-center"
        >
          <IconX />
        </button>
      </div>
      {errors.name && <p className="text-[11px] text-[#f87171]">{errors.name.message}</p>}
      <ColorPicker value={color} onChange={setColor} />
    </form>
  );
}

// ─── Cluster card ─────────────────────────────────────────────────────────────

function ClusterCard({ cluster }: { cluster: ClusterResponse }) {
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { mutate: del, isPending: deleting } = useDeleteCluster();

  if (editing) {
    return <EditClusterRow cluster={cluster} onCancel={() => setEditing(false)} />;
  }

  if (confirmDelete) {
    return (
      <div className="rounded-xl border border-[#f87171]/20 bg-[#f87171]/5 p-4 flex items-center gap-3">
        <span
          className="w-3 h-3 rounded-full shrink-0"
          style={{ background: cluster.color }}
          aria-hidden="true"
        />
        <p className="flex-1 font-mono text-sm text-[#f87171]">
          Remove <strong>{cluster.name}</strong>? Tickers will become unassigned.
        </p>
        <button
          onClick={() => del(cluster.id)}
          disabled={deleting}
          className="h-7 px-3 bg-[#f87171] hover:bg-[#ef4444] text-white font-mono font-bold text-xs rounded-lg transition-colors disabled:opacity-50"
        >
          {deleting ? '…' : 'Remove'}
        </button>
        <button
          onClick={() => setConfirmDelete(false)}
          className="h-7 px-2 text-[#8a95a8] hover:text-[#e8edf5] text-xs"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="group rounded-xl border border-[#1e2a3f] bg-[#0d1421] p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-center gap-3">
        <span
          className="w-3 h-3 rounded-full shrink-0"
          style={{ background: cluster.color }}
          aria-label={`Colour ${cluster.color}`}
        />
        <p className="flex-1 font-mono font-semibold text-sm text-[#e8edf5]">{cluster.name}</p>
        <span className="text-[10px] text-[#4a5568] font-mono">
          {cluster.tickers.length} ticker{cluster.tickers.length !== 1 ? 's' : ''}
        </span>
        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          <button
            onClick={() => setEditing(true)}
            aria-label={`Edit ${cluster.name}`}
            className="w-7 h-7 rounded-lg text-[#4a90d9] hover:bg-[#4a90d9]/10 flex items-center justify-center transition-colors"
          >
            <IconPencil />
          </button>
          <button
            onClick={() => setConfirmDelete(true)}
            aria-label={`Remove ${cluster.name}`}
            className="w-7 h-7 rounded-lg text-[#3a4a5e] hover:text-[#f87171] hover:bg-[#f87171]/10 flex items-center justify-center transition-colors"
          >
            <IconTrash />
          </button>
        </div>
      </div>

      {/* Ticker chips */}
      {cluster.tickers.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {cluster.tickers.map((t) => (
            <span
              key={t.id}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono font-semibold"
              style={{
                background: `${cluster.color}18`,
                color: cluster.color,
                border: `1px solid ${cluster.color}30`,
              }}
            >
              {t.ticker}
              <span className="font-normal text-[9px] opacity-60">{t.shares}</span>
            </span>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-[#3a4a5e] italic">
          No tickers assigned — add tickers via the Portfolio tab.
        </p>
      )}
    </div>
  );
}

// ─── Clusters list ────────────────────────────────────────────────────────────

function ClustersList() {
  const { data: clusters, isLoading } = useClusters();

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-20 rounded-xl border border-[#1e2a3f] bg-[#0d1421] animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (!clusters || clusters.length === 0) {
    return (
      <div className="py-10 text-center rounded-xl border border-dashed border-[#1e2a3f]">
        <p className="text-sm text-[#4a5568]">No clusters yet</p>
        <p className="text-xs text-[#2d3f5c] mt-1">Create one using the form on the left</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {clusters.map((c) => (
        <ClusterCard key={c.id} cluster={c} />
      ))}
    </div>
  );
}

// ─── Main screen ──────────────────────────────────────────────────────────────

function ClustersContent() {
  return (
    <div className="atlas-portfolio-main" style={{ padding: '20px 24px' }}>
      {/* Page heading */}
      <div className="mb-5">
        <h1
          className="font-mono font-bold text-base tracking-widest uppercase"
          style={{ color: '#e8edf5' }}
        >
          Clusters
        </h1>
        <p className="mt-0.5 text-xs" style={{ color: '#4a5568' }}>
          Group your holdings into named clusters and assign tickers when adding positions.
        </p>
      </div>

      <div
        className="grid gap-6"
        style={{ gridTemplateColumns: 'minmax(0, 320px) minmax(0, 1fr)' }}
      >
        {/* Left: create form */}
        <div>
          <CreateClusterForm />
        </div>

        {/* Right: cluster cards */}
        <div>
          <p
            className="font-mono text-[10px] uppercase tracking-[0.15em] mb-3"
            style={{ color: '#3a4a5e' }}
          >
            Your Clusters
          </p>
          <ClustersList />
        </div>
      </div>
    </div>
  );
}

export function ClustersScreen() {
  return <ClustersContent />;
}

