'use client';

import { LogoutButton } from '@/components/auth/logout-button';
import { useTickers, useSyncTickers } from '@/lib/hooks/use-tickers';
import type { TickerResponse } from '@/lib/schemas/ticker';
import { cn } from '@/lib/utils';
import type { PortfolioNavItem, PortfolioScreenData, PortfolioSummaryRow } from '@/types/portfolio';

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

              return (
                <article className="atlas-portfolio-holding" key={t.id}>
                  <div className="atlas-portfolio-holding-row">
                    <span className="atlas-portfolio-holding-symbol">{t.ticker}</span>
                    <span className="atlas-portfolio-holding-value">{formatValue(t)}</span>
                  </div>
                  <div className="atlas-portfolio-progress">
                    <span
                      className={cn('atlas-portfolio-progress-bar', `is-${progressTone}`)}
                      style={{ width: `${pct}%` }}
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

export function AtlasActionsRail({
  actions,
  summaryRows,
  summaryTitle,
  title,
}: {
  actions: PortfolioScreenData['actions'];
  summaryRows: PortfolioScreenData['summaryRows'];
  summaryTitle: string;
  title: string;
}) {
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
        <h2 className="atlas-portfolio-side-title">{summaryTitle}</h2>
        <div>
          {summaryRows.map((row) => (
            <SummaryRow key={row.label} row={row} />
          ))}
        </div>
      </section>
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
