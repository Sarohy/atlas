'use client';

import { cn } from '@/lib/utils';
import { useFramework30 } from '@/lib/hooks/use-framework30';
import type { DrawdownState, Framework30Result } from '@/lib/schemas/framework30';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Drawdown threshold at which CARVEOUT state begins (%). */
const CARVEOUT_THRESHOLD_PCT = 15;

/** Drawdown threshold at which HARD_HALT state begins (%). */
const HARD_HALT_THRESHOLD_PCT = 25;

/** Maximum drawdown % for progress bar scale. */
const DRAWDOWN_BAR_MAX_PCT = 30;

/** State chip labels. */
const STATE_LABEL: Record<DrawdownState, string> = {
  NORMAL: 'NORMAL',
  CARVEOUT: 'CARVEOUT',
  HARD_HALT: 'HARD HALT',
  UNKNOWN: 'UNKNOWN',
};

/** State chip CSS classes. */
const STATE_CHIP_CLASS: Record<DrawdownState, string> = {
  NORMAL: 'is-f30-normal',
  CARVEOUT: 'is-f30-carveout',
  HARD_HALT: 'is-f30-hard-halt',
  UNKNOWN: 'is-f30-unknown',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatUsd(val: number | null): string {
  if (val === null) return '—';
  if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
  return `$${val.toFixed(0)}`;
}

function formatPct(val: number | null): string {
  if (val === null) return '—';
  return `${(val * 100).toFixed(2)}%`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: string;
}) {
  return (
    <div className="atlas-f30-stat-card">
      <span className="atlas-f30-stat-label">{label}</span>
      <span className={cn('atlas-f30-stat-value', highlight ?? '')}>{value}</span>
    </div>
  );
}

function DrawdownBar({ drawdownPct }: { drawdownPct: number | null }) {
  const pct = drawdownPct !== null ? Math.abs(drawdownPct) * 100 : null;
  const fillWidth =
    pct !== null ? Math.min(100, (pct / DRAWDOWN_BAR_MAX_PCT) * 100) : 0;
  const carveoutLeft = (CARVEOUT_THRESHOLD_PCT / DRAWDOWN_BAR_MAX_PCT) * 100;
  const haltLeft = (HARD_HALT_THRESHOLD_PCT / DRAWDOWN_BAR_MAX_PCT) * 100;

  const barClass =
    pct === null
      ? 'is-f30-bar-unknown'
      : pct >= HARD_HALT_THRESHOLD_PCT
        ? 'is-f30-bar-halt'
        : pct >= CARVEOUT_THRESHOLD_PCT
          ? 'is-f30-bar-carveout'
          : 'is-f30-bar-normal';

  return (
    <div className="atlas-f30-drawdown-bar-section" data-testid="f30-drawdown-bar">
      <div className="atlas-f30-drawdown-bar-header">
        <span className="atlas-f30-drawdown-bar-label">Portfolio Drawdown from 90-Day Peak</span>
        {pct !== null && (
          <span className="atlas-f30-drawdown-bar-pct">{pct.toFixed(2)}%</span>
        )}
      </div>
      <div className="atlas-f30-drawdown-bar-track">
        <div
          className={cn('atlas-f30-drawdown-bar-fill', barClass)}
          style={{ width: `${fillWidth}%` }}
        />
        {/* Carveout marker at 15% */}
        <div
          className="atlas-f30-drawdown-bar-marker atlas-f30-drawdown-bar-marker--amber"
          style={{ left: `${carveoutLeft}%` }}
          title="15% — CARVEOUT threshold"
        />
        {/* Hard halt marker at 25% */}
        <div
          className="atlas-f30-drawdown-bar-marker atlas-f30-drawdown-bar-marker--red"
          style={{ left: `${haltLeft}%` }}
          title="25% — HARD HALT threshold"
        />
      </div>
      <div className="atlas-f30-drawdown-bar-labels">
        <span>0%</span>
        <span style={{ position: 'absolute', left: `${carveoutLeft}%`, transform: 'translateX(-50%)' }}>
          15%
        </span>
        <span style={{ position: 'absolute', left: `${haltLeft}%`, transform: 'translateX(-50%)' }}>
          25%
        </span>
        <span>{DRAWDOWN_BAR_MAX_PCT}%</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

// Framework 30 is portfolio-level — no ticker prop needed.
type Framework30CardProps = Record<string, never>;

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 30 — Max Drawdown Gate card.
 *
 * Portfolio-level. Sections:
 *   1. Header + state chip
 *   2. Stat cards (NAV / Peak NAV / Drawdown % / Drawdown $)
 *   3. Drawdown progress bar (markers at 15% and 25%)
 *   4. Gate rules panel (NORMAL / CARVEOUT / HARD_HALT / UNKNOWN)
 *   5. Stale / missing positions list (if any)
 *   6. Warning messages (if any)
 *   7. Recovery status (if active)
 *   8. Data age footer
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function Framework30Card(_props: Framework30CardProps) {
  const { data, isLoading, isError, error } = useFramework30();
  const errorMsg =
    error instanceof Error ? error.message : 'Failed to load drawdown gate data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-f30-panel"
      data-testid="framework30-card"
    >
      {/* ── Section 1: Header + state chip ── */}
      <header className="atlas-f30-header">
        <div className="atlas-f30-header-left">
          <h2 className="atlas-frameworks-panel-title">Framework 30</h2>
          <span className="atlas-fws-subtitle">Max Drawdown Gate</span>
        </div>
        {data !== undefined && (
          <span
            className={cn('atlas-f30-state-chip', STATE_CHIP_CLASS[data.drawdown_state])}
            data-testid="f30-state-chip"
          >
            {STATE_LABEL[data.drawdown_state]}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="f30-loading">
            Loading drawdown data…
          </p>
        )}

        {isError && (
          <p
            className="atlas-fws-state-msg atlas-fws-state-msg--error"
            data-testid="f30-error"
          >
            {errorMsg}
          </p>
        )}

        {!isLoading && !isError && data !== undefined && (
          <Framework30Content data={data} />
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Content sub-component
// ---------------------------------------------------------------------------

function Framework30Content({ data }: { data: Framework30Result }) {
  const drawdownPctDisplay = formatPct(data.drawdown_pct);
  const drawdownClass =
    data.drawdown_pct === null
      ? ''
      : Math.abs(data.drawdown_pct) * 100 >= HARD_HALT_THRESHOLD_PCT
        ? 'is-f30-halt-value'
        : Math.abs(data.drawdown_pct) * 100 >= CARVEOUT_THRESHOLD_PCT
          ? 'is-f30-carveout-value'
          : 'is-f30-normal-value';

  return (
    <div className="atlas-f30-content" data-testid="f30-content">
      {/* ── Section 2: Stat cards ── */}
      <div className="atlas-f30-stats-row" data-testid="f30-stats">
        <StatCard label="Current NAV" value={formatUsd(data.current_nav)} />
        <StatCard label="90-Day Peak" value={formatUsd(data.peak_nav_90d)} />
        <StatCard
          label="Drawdown"
          value={drawdownPctDisplay}
          highlight={drawdownClass}
        />
        <StatCard label="Drawdown $" value={formatUsd(data.drawdown_usd)} />
      </div>

      {/* ── Section 3: Drawdown progress bar ── */}
      <DrawdownBar drawdownPct={data.drawdown_pct} />

      {/* ── Section 4: Gate rules panel ── */}
      <div className="atlas-f30-rules-panel" data-testid="f30-rules">
        <div className="atlas-f30-rules-header">
          <span className="atlas-f30-rules-title">Gate Rules</span>
          <span className={cn('atlas-f30-state-chip-sm', STATE_CHIP_CLASS[data.drawdown_state])}>
            {STATE_LABEL[data.drawdown_state]}
          </span>
        </div>
        <div className="atlas-f30-rule-row">
          <span className="atlas-f30-rule-label">Adds Permitted</span>
          <span
            className={cn(
              'atlas-f30-rule-value',
              data.adds_permitted ? 'is-f30-green' : 'is-f30-red',
            )}
            data-testid="f30-adds-permitted"
          >
            {data.adds_permitted ? 'YES' : 'NO'}
          </span>
        </div>
        <div className="atlas-f30-rule-row">
          <span className="atlas-f30-rule-label">LEAPS Permitted</span>
          <span
            className={cn(
              'atlas-f30-rule-value',
              data.leaps_permitted ? 'is-f30-green' : 'is-f30-red',
            )}
            data-testid="f30-leaps-permitted"
          >
            {data.leaps_permitted ? 'YES' : 'NO'}
          </span>
        </div>
        {data.leaps_position_cap_pct !== null && (
          <div className="atlas-f30-rule-row">
            <span className="atlas-f30-rule-label">LEAPS Cap</span>
            <span className="atlas-f30-rule-value">{(data.leaps_position_cap_pct * 100).toFixed(0)}%</span>
          </div>
        )}
        <div className="atlas-f30-rule-row">
          <span className="atlas-f30-rule-label">All Signals Halted</span>
          <span
            className={cn(
              'atlas-f30-rule-value',
              data.all_signals_halted ? 'is-f30-red' : '',
            )}
          >
            {data.all_signals_halted ? 'YES' : 'NO'}
          </span>
        </div>
        {data.sizing_multiplier !== null && (
          <div className="atlas-f30-rule-row">
            <span className="atlas-f30-rule-label">Sizing Multiplier</span>
            <span className="atlas-f30-rule-value">{data.sizing_multiplier.toFixed(2)}×</span>
          </div>
        )}
      </div>

      {/* ── Section 5: Stale / missing positions ── */}
      {(data.stale_positions.length > 0 || data.missing_positions.length > 0) && (
        <div className="atlas-f30-positions-alert" data-testid="f30-positions-alert">
          {data.stale_positions.length > 0 && (
            <p className="atlas-f30-positions-stale">
              Stale prices: {data.stale_positions.join(', ')}
            </p>
          )}
          {data.missing_positions.length > 0 && (
            <p className="atlas-f30-positions-missing">
              Missing prices: {data.missing_positions.join(', ')}
            </p>
          )}
        </div>
      )}

      {/* ── Section 6: Warning messages ── */}
      {data.warning_messages.length > 0 && (
        <ul className="atlas-f30-warnings" data-testid="f30-warnings">
          {data.warning_messages.map((msg, idx) => (
            <li key={idx} className="atlas-f30-warning-item">
              {msg}
            </li>
          ))}
        </ul>
      )}

      {/* ── Section 7: Recovery status ── */}
      {data.recovery_active && (
        <div className="atlas-f30-recovery-panel" data-testid="f30-recovery">
          <p className="atlas-f30-recovery-label">RECOVERY PERIOD ACTIVE</p>
          {data.recovery_days_remaining !== null && (
            <p className="atlas-f30-recovery-days">
              {data.recovery_days_remaining} day{data.recovery_days_remaining === 1 ? '' : 's'} remaining
            </p>
          )}
        </div>
      )}

      {/* ── Section 8: Data age footer ── */}
      <p className="atlas-f30-footer" data-testid="f30-footer">
        {data.cache_hit ? 'cached' : 'live'} · {data.data_age_minutes.toFixed(0)} min ago
        {!data.nav_data_complete && ' · NAV incomplete'}
      </p>
    </div>
  );
}
