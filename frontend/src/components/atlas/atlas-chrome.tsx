'use client';

import { useState } from 'react';
import { LogoutButton } from '@/components/auth/logout-button';
import { useAdjustCash, usePortfolioSummary } from '@/lib/hooks/use-portfolio-summary';
import { useTickers, useSyncTickers } from '@/lib/hooks/use-tickers';
import { useClusters } from '@/lib/hooks/use-clusters';
import type { PortfolioSummary } from '@/lib/schemas/portfolio-summary';
import type { ClusterResponse } from '@/lib/schemas/cluster';
import type { TickerResponse } from '@/lib/schemas/ticker';
import { cn } from '@/lib/utils';
import type {
  PortfolioAccentTone,
  PortfolioMetricCard,
  PortfolioNavItem,
  PortfolioScreenData,
  PortfolioSummaryRow,
  PortfolioValueTone,
} from '@/types/portfolio';

// ─── Format helpers ───────────────────────────────────────────────────────────

/** Format a raw dollar value as $X.XXM (millions, 2 d.p.). */
function fmtM(v: number): string {
  return `$${(v / 1_000_000).toFixed(2)}M`;
}

/** Format an absolute dollar amount compactly (K / M). */
function fmtAbs(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `$${Math.round(v / 1_000)}K`;
  return `$${Math.round(v)}`;
}

/** Build the right-sidebar summary rows from a live PortfolioSummary. */
function buildSummaryRows(s: PortfolioSummary): PortfolioSummaryRow[] {
  const deployableTone: PortfolioAccentTone = s.deployable >= 0 ? 'cyan' : 'red';
  const deployableText =
    s.deployable >= 0 ? `${fmtM(s.deployable)} above floor` : `${fmtM(-s.deployable)} below floor`;

  return [
    { label: 'Total NAV', tone: 'cyan', value: fmtM(s.total_nav) },
    {
      label: 'Invested',
      tone: 'default',
      value: `${fmtM(s.invested_value)} (${s.invested_pct.toFixed(1)}%)`,
    },
    {
      label: 'Cash',
      tone: 'green',
      value: `${fmtM(s.cash_balance)} (${s.cash_pct.toFixed(1)}%)`,
    },
    {
      label: 'Cash floor',
      tone: 'green',
      value: `${fmtM(s.cash_floor)} (${s.cash_floor_pct.toFixed(1)}%)`,
    },
    { label: 'Deployable', tone: deployableTone, value: deployableText },
    {
      label: 'Beta',
      tone: 'default',
      value: `${s.beta_total?.toFixed(2) ?? '—'} total · ${s.beta_invested?.toFixed(2) ?? '—'} invested`,
    },
  ];
}

/** Build the top metric cards from a live PortfolioSummary. */
function buildMetricCards(s: PortfolioSummary): PortfolioMetricCard[] {
  const dayChangeTone: PortfolioValueTone =
    s.day_change == null ? 'default' : s.day_change >= 0 ? 'green' : 'red';
  const dayChangeText =
    s.day_change != null
      ? `${s.day_change >= 0 ? '↑' : '↓'} ${fmtAbs(Math.abs(s.day_change))} today`
      : '—';

  return [
    {
      detail: dayChangeText,
      label: 'Total Portfolio',
      tone: 'cyan',
      value: fmtM(s.total_nav),
      valueTone: dayChangeTone,
    },
    {
      detail: `${s.cash_pct.toFixed(1)}% · floor ${fmtM(s.cash_floor)}`,
      label: 'Cash Reserve',
      tone: 'green',
      value: fmtM(s.cash_balance),
      valueTone: 'green',
    },
    {
      detail: `incl. cash · ${s.beta_invested?.toFixed(2) ?? '—'} invested`,
      label: 'Portfolio Beta',
      tone: 'yellow',
      value: s.beta_total?.toFixed(2) ?? '—',
    },
  ];
}

export function AtlasHeader({ appTitle }: { appTitle: string }) {
  const { mutate: sync, isPending: isSyncing } = useSyncTickers();

  return (
    <header className="atlas-portfolio-topbar">
      <div className="atlas-portfolio-wordmark">{appTitle}</div>
      <div className="flex items-center gap-3">
        <button
          onClick={() => sync()}
          disabled={isSyncing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold bg-[#1e2a3f] border border-[#2d3f5c] text-[#4a90d9] rounded hover:bg-[#253450] transition-colors disabled:opacity-40"
          type="button"
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
        <LogoutButton />
      </div>
    </header>
  );
}

export function AtlasNavigation({ labels }: { labels: readonly PortfolioNavItem[] }) {
  return (
    <nav aria-label="Primary" className="atlas-portfolio-nav">
      {labels.map((item) => (
        <a
          aria-current={item.isActive ? 'page' : undefined}
          className={cn('atlas-portfolio-nav-item', item.isActive && 'is-active')}
          href={item.href}
          key={item.label}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

export function AtlasHoldingsRail() {
  const { data: tickers, isLoading } = useTickers();
  const { data: clusters } = useClusters();

  /** Map of cluster id → hex colour string, e.g. '#4a90d9'. */
  const clusterColorMap = new Map((clusters ?? []).map((c) => [c.id, c.color]));

  const maxValue = Math.max(
    ...(tickers ?? []).map((t) => t.position_value ?? 0),
    1, // avoid division by zero
  );

  const totalValue = (tickers ?? []).reduce((sum, t) => sum + (t.position_value ?? 0), 0);

  function formatValue(t: TickerResponse): string {
    if (t.position_value != null) {
      return t.position_value.toLocaleString('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
      });
    }
    return `${t.shares} shs`;
  }

  function formatAllocation(t: TickerResponse): string {
    const parts: string[] = [];
    if (totalValue > 0 && t.position_value != null) {
      parts.push(`${((t.position_value / totalValue) * 100).toFixed(1)}%`);
    }
    if (t.beta != null) parts.push(`\u03b2${t.beta.toFixed(2)}`);
    return parts.join(' \u00b7 ') || t.company_name;
  }

  function formatDayChange(t: TickerResponse): string {
    if (t.day_change_pct == null) return '\u2014';
    return `${t.day_change_pct >= 0 ? '+' : ''}${t.day_change_pct.toFixed(1)}%`;
  }

  return (
    <aside className="atlas-portfolio-side atlas-portfolio-side--left">
      <section className="atlas-portfolio-side-section">
        <h2 className="atlas-portfolio-side-title">Holdings</h2>
        <div>
          {isLoading ? (
            Array.from({ length: 5 }, (_, i) => (
              <article className="atlas-portfolio-holding" key={i}>
                <div className="atlas-portfolio-holding-row">
                  <span className="h-3 w-12 rounded bg-[#1e2a3f] animate-pulse" />
                  <span className="h-3 w-16 rounded bg-[#1e2a3f] animate-pulse" />
                </div>
                <div className="atlas-portfolio-progress">
                  <span className="atlas-portfolio-progress-bar is-cyan" style={{ width: '50%' }} />
                </div>
                <div className="atlas-portfolio-holding-row atlas-portfolio-holding-row--meta">
                  <span className="h-2 w-20 rounded bg-[#1e2a3f] animate-pulse" />
                  <span className="h-2 w-10 rounded bg-[#1e2a3f] animate-pulse" />
                </div>
              </article>
            ))
          ) : (tickers ?? []).length === 0 ? (
            <p className="atlas-portfolio-holding-meta px-2 py-3">No holdings yet.</p>
          ) : (
            (tickers ?? []).map((t) => {
              const pct =
                t.position_value != null ? Math.round((t.position_value / maxValue) * 100) : 0;
              const changePct = t.day_change_pct;
              const dayChangeTone =
                changePct == null ? 'default' : changePct >= 0 ? 'green' : 'red';
              const progressTone = changePct == null || changePct >= 0 ? 'cyan' : 'red';
              const clusterColor =
                t.cluster_id != null ? clusterColorMap.get(t.cluster_id) : undefined;

              return (
                <article className="atlas-portfolio-holding" key={t.id}>
                  <div className="atlas-portfolio-holding-row">
                    <span className="atlas-portfolio-holding-symbol">{t.ticker}</span>
                    <span className="atlas-portfolio-holding-value">{formatValue(t)}</span>
                  </div>
                  <div className="atlas-portfolio-progress">
                    <span
                      className={cn(
                        'atlas-portfolio-progress-bar',
                        clusterColor == null && `is-${progressTone}`,
                      )}
                      style={{
                        width: `${pct}%`,
                        ...(clusterColor != null && { backgroundColor: clusterColor }),
                      }}
                    />
                  </div>
                  <div className="atlas-portfolio-holding-row atlas-portfolio-holding-row--meta">
                    <span className="atlas-portfolio-holding-meta">{formatAllocation(t)}</span>
                    <span className={cn('atlas-portfolio-holding-change', `is-${dayChangeTone}`)}>
                      {formatDayChange(t)}
                    </span>
                  </div>
                </article>
              );
            })
          )}
        </div>
      </section>
    </aside>
  );
}

// ─── Cluster summary section ─────────────────────────────────────────────────

/** Per-cluster allocation row rendered inside the right rail. */
function ClusterRow({
  label,
  color,
  value,
  pct,
  count,
}: {
  label: string;
  color: string;
  value: number;
  pct: number;
  count: number;
}) {
  return (
    <div className="atlas-portfolio-summary-row" style={{ alignItems: 'flex-start', paddingBlock: '5px' }}>
      <span className="atlas-portfolio-summary-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span
          style={{
            display: 'inline-block',
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: color,
            flexShrink: 0,
          }}
        />
        <span>{label}</span>
        <span style={{ fontSize: '0.6rem', color: '#3a4a5e', marginLeft: '2px' }}>
          {count} {count === 1 ? 'ticker' : 'tickers'}
        </span>
      </span>
      <span className="atlas-portfolio-summary-value" style={{ textAlign: 'right' }}>
        {value >= 1_000_000
          ? `$${(value / 1_000_000).toFixed(2)}M`
          : value >= 1_000
            ? `$${Math.round(value / 1_000)}K`
            : `$${Math.round(value)}`}
        <span style={{ display: 'block', fontSize: '0.6rem', color: '#4a5568' }}>
          {pct.toFixed(1)}%
        </span>
      </span>
    </div>
  );
}

/** Breaks down portfolio value by cluster + unassigned row. */
function ClusterSummarySection({
  clusters,
  tickers,
}: {
  clusters: ClusterResponse[];
  tickers: TickerResponse[];
}) {
  const totalValue = tickers.reduce((s, t) => s + (t.position_value ?? 0), 0);

  // Build a set of ticker ids that belong to at least one cluster.
  const assignedIds = new Set(clusters.flatMap((c) => c.tickers.map((t) => t.id)));

  const unassigned = tickers.filter((t) => !assignedIds.has(t.id));
  const unassignedValue = unassigned.reduce((s, t) => s + (t.position_value ?? 0), 0);

  const rows = clusters
    .map((c) => ({
      id: c.id,
      label: c.name,
      color: c.color,
      value: c.tickers.reduce((s, t) => s + (t.position_value ?? 0), 0),
      count: c.tickers.length,
    }))
    .filter((r) => r.count > 0)
    .sort((a, b) => b.value - a.value);

  if (rows.length === 0 && unassigned.length === 0) return null;

  return (
    <section className="atlas-portfolio-side-section">
      <h2 className="atlas-portfolio-side-title">Cluster Breakdown</h2>
      <div>
        {rows.map((r) => (
          <ClusterRow
            key={r.id}
            label={r.label}
            color={r.color}
            value={r.value}
            pct={totalValue > 0 ? (r.value / totalValue) * 100 : 0}
            count={r.count}
          />
        ))}
        {unassigned.length > 0 && (
          <ClusterRow
            label="Unassigned"
            color="#3a4a5e"
            value={unassignedValue}
            pct={totalValue > 0 ? (unassignedValue / totalValue) * 100 : 0}
            count={unassigned.length}
          />
        )}
      </div>
    </section>
  );
}

export function AtlasActionsRail({
  actions,
  title,
}: {
  actions: PortfolioScreenData['actions'];
  title: string;
}) {
  const { data: summary, isLoading } = usePortfolioSummary();
  const { data: clusters } = useClusters();
  const { data: tickers } = useTickers();
  const summaryRows = summary ? buildSummaryRows(summary) : [];

  return (
    <aside className="atlas-portfolio-side atlas-portfolio-side--right">
      <section className="atlas-portfolio-side-section">
        <h2 className="atlas-portfolio-side-title">{title}</h2>
        <div>
          {actions.map((action) => (
            <article className="atlas-portfolio-action" key={`${action.title}-${action.metadata}`}>
              <span className={cn('atlas-portfolio-action-dot', `is-${action.tone}`)} />
              <div className="atlas-portfolio-action-copy">
                <p className="atlas-portfolio-action-text">
                  <strong>{action.title}</strong> {action.description}
                </p>
                <p className="atlas-portfolio-action-meta">{action.metadata}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="atlas-portfolio-side-section">
        <h2 className="atlas-portfolio-side-title">Portfolio Summary</h2>
        <div>
          {isLoading
            ? Array.from({ length: 5 }, (_, i) => (
                <div className="atlas-portfolio-summary-row" key={i}>
                  <span className="h-3 w-20 rounded bg-[#1e2a3f] animate-pulse" />
                  <span className="h-3 w-16 rounded bg-[#1e2a3f] animate-pulse" />
                </div>
              ))
            : summaryRows.map((row) => <SummaryRow key={row.label} row={row} />)}
        </div>
      </section>

      {clusters && tickers && (
        <ClusterSummarySection clusters={clusters} tickers={tickers} />
      )}
    </aside>
  );
}

function SummaryRow({ row }: { row: PortfolioSummaryRow }) {
  return (
    <div className="atlas-portfolio-summary-row">
      <span className="atlas-portfolio-summary-label">{row.label}</span>
      <span className={cn('atlas-portfolio-summary-value', getSummaryToneClass(row.tone))}>
        {row.value}
      </span>
    </div>
  );
}

function getSummaryToneClass(tone: PortfolioSummaryRow['tone']) {
  return tone === 'default' ? undefined : `is-${tone}`;
}

// ─── Live metric cards ────────────────────────────────────────────────────────

/** Replaces the static AtlasMetricsGrid with data fetched from the portfolio summary API. */
export function LiveMetricsGrid() {
  const { data: summary, isLoading } = usePortfolioSummary();

  if (isLoading || !summary) {
    return (
      <section className="atlas-portfolio-metrics">
        {Array.from({ length: 3 }, (_, i) => (
          <article className="atlas-portfolio-metric-card is-cyan" key={i}>
            <span className="h-3 w-24 rounded bg-[#1e2a3f] animate-pulse block mb-2" />
            <span className="h-6 w-16 rounded bg-[#1e2a3f] animate-pulse block mb-2" />
            <span className="h-3 w-28 rounded bg-[#1e2a3f] animate-pulse block" />
          </article>
        ))}
      </section>
    );
  }

  const cards = buildMetricCards(summary);

  return (
    <section className="atlas-portfolio-metrics">
      {cards.map((card) => (
        <article className={cn('atlas-portfolio-metric-card', `is-${card.tone}`)} key={card.label}>
          <p className="atlas-portfolio-metric-label">{card.label}</p>
          <p
            className={cn(
              'atlas-portfolio-metric-value',
              card.valueTone ? `is-${card.valueTone}` : undefined,
            )}
          >
            {card.value}
          </p>
          <p className="atlas-portfolio-metric-detail">{card.detail}</p>
        </article>
      ))}
    </section>
  );
}

// ─── Live cash panel ──────────────────────────────────────────────────────────

/** Cash panel that reads live balance and lets the user add or subtract incrementally. */
export function LiveCashPanel() {
  const { data: summary, isLoading } = usePortfolioSummary();
  const { mutate: adjustCash, isPending, isError, error } = useAdjustCash();

  const [deltaInput, setDeltaInput] = useState('');

  const delta = deltaInput !== '' ? parseFloat(deltaInput) : null;
  const previewBalance =
    delta !== null && !isNaN(delta) && summary ? Math.max(0, summary.cash_balance + delta) : null;

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (delta === null || isNaN(delta)) return;
    adjustCash(delta, { onSuccess: () => setDeltaInput('') });
  }

  const balanceText = isLoading ? '…' : summary ? fmtM(summary.cash_balance) : '—';
  const floorText = isLoading
    ? '…'
    : summary
      ? `${fmtM(summary.cash_floor)} · ${summary.cash_floor_pct.toFixed(1)}% floor`
      : '—';

  return (
    <section className="atlas-portfolio-panel">
      <div className="atlas-portfolio-panel-header atlas-portfolio-panel-header--cash">
        <h2 className="atlas-portfolio-panel-title">Cash Reserve</h2>
      </div>
      <div className="atlas-portfolio-cash-card">
        <div className="atlas-portfolio-cash-icon" aria-hidden="true">
          $
        </div>
        <p className="atlas-portfolio-cash-label">Current Balance</p>
        <p className="atlas-portfolio-cash-value">{balanceText}</p>
        {previewBalance !== null && (
          <p
            className="atlas-portfolio-cash-label"
            style={{ marginTop: '0.3rem', fontSize: '0.7rem' }}
          >
            → {fmtM(previewBalance)}
          </p>
        )}
        <p
          className="atlas-portfolio-cash-label"
          style={{ marginTop: '0.4rem', fontSize: '0.7rem' }}
        >
          {floorText}
        </p>
      </div>
      <form onSubmit={handleSubmit}>
        <div className="atlas-portfolio-cash-input-row">
          <input
            aria-label="Cash adjustment amount"
            className="atlas-portfolio-cash-input"
            disabled={isPending}
            onChange={(e) => setDeltaInput(e.target.value)}
            placeholder="+ add / − subtract…"
            step="any"
            type="number"
            value={deltaInput}
          />
          <button
            aria-label="Apply cash adjustment"
            className="atlas-portfolio-cash-submit"
            disabled={isPending || deltaInput === ''}
            type="submit"
          >
            {isPending ? '…' : '›'}
          </button>
        </div>
        {isError && (
          <p className="font-mono px-1 pt-1" style={{ fontSize: '0.65rem', color: '#f87171' }}>
            {error instanceof Error ? error.message : 'Failed to update.'}
          </p>
        )}
      </form>
    </section>
  );
}
