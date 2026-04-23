'use client';

import { useConvictionAction } from '@/lib/hooks/use-conviction-action';
import type { ConvictionActionResponse, Tier } from '@/lib/schemas/conviction-action';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Number of exit-cycle closes that trigger the exit rule. */
const EXIT_CYCLE_TRIGGER = 2;

/** Tier color lookup — overrides inline style when available via CSS class. */
const TIER_COLOR_CLASS: Record<Tier, string> = {
  TIER_1_CORE: 'is-green',
  GREY_ZONE: 'is-purple',
  TIER_2: 'is-blue',
  TIER_3: 'is-amber',
  WATCHLIST: 'is-red',
};

const SIZE_STATUS_LABEL: Record<string, string> = {
  UNDERWEIGHT: 'Underweight',
  IN_RANGE: 'In Range',
  OVERWEIGHT: 'Overweight',
  NO_POSITION: 'No Position',
};

const CONSENSUS_STATUS_LABEL: Record<string, string> = {
  NOT_REQUIRED: 'Not Required',
  PENDING: 'Pending',
  CONFIRMED: 'Confirmed',
  FAILED: 'Failed',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type ConvictionActionPanelProps = {
  /** Active ticker driven by the shared selector above the panels. */
  ticker: string;
  /**
   * The score already displayed by the F1 panel: `final_score + regime_modifier`
   * clamped to 0–100. Passed directly to the backend so the regime delta is
   * not applied a second time.
   */
  adjustedScore: number | undefined;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 6 — Conviction Action panel (v7.3.4 Watchlist Tier Structure).
 *
 * Displays the conviction tier, position sizing guidance, consensus status,
 * cluster info, LEAPS eligibility, and exit cycle counter for a given ticker.
 */
export function ConvictionActionPanel({ ticker, adjustedScore }: ConvictionActionPanelProps) {
  const activeTicker = ticker.trim().length > 0;
  const { data, isLoading, isError, error } = useConvictionAction(ticker, adjustedScore);
  const hasData = activeTicker && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load conviction data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-regime-panel atlas-conviction-panel"
      data-testid="conviction-action-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 6</h2>
        <span className="atlas-fws-subtitle">Score → Conviction Tier</span>
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="conviction-loading">
            Computing conviction tier...
          </p>
        )}
        {isError && (
          <p
            className="atlas-fws-state-msg atlas-fws-state-msg--error"
            data-testid="conviction-error"
          >
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && hasData && <ConvictionContent data={data} />}
        {!isLoading && !isError && !hasData && activeTicker && (
          <p className="atlas-fws-state-msg" data-testid="conviction-empty">
            No conviction data available for {ticker}.
          </p>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Content component — 8 sections
// ---------------------------------------------------------------------------

/** Named constants for per-tier bottom messages. */
const TIER_MESSAGES: Record<string, string> = {
  TIER_1_CORE: 'Hold full position and add on dips',
  GREY_ZONE: 'Run 3-AI consensus before adding',
  TIER_2: 'GTC adds permitted — size within tier',
  TIER_3: 'Satellite only — max size apply',
  WATCHLIST: 'No capital — monitor every Friday',
};

function getTierMessage(tier: string): string {
  return TIER_MESSAGES[tier] ?? tier;
}

function ConvictionContent({ data }: { data: ConvictionActionResponse }) {
  const tierColorClass = TIER_COLOR_CLASS[data.tier] ?? '';
  const bandLabel = data.score_band_max !== null
    ? `${data.score_band_min}–${data.score_band_max}`
    : `${data.score_band_min}+`;
  const sizeLabel = data.size_min_pct === 0 && data.size_max_pct === 0
    ? '0% NAV'
    : `${data.size_min_pct}–${data.size_max_pct}% NAV`;
  const bottomMessage = data.adds_permitted
    ? getTierMessage(data.tier)
    : `Adds blocked — ${data.adds_blocked_reason}`;

  return (
    <div className="atlas-conviction-content" data-testid="conviction-content">

      {/* ── Section 1: Tier label ──────────────────────────────────────── */}
      <p
        className={cn('atlas-conviction-tier-label', tierColorClass)}
        data-testid="conviction-tier-label"
        style={{ color: data.tier_color }}
      >
        {data.tier_label}
      </p>

      {/* ── Section 2: Score band + size range ───────────────────────────── */}
      <div className="atlas-conviction-info-row">
        <div className="atlas-conviction-info-box" data-testid="conviction-score-band">
          <span className="atlas-conviction-info-box__label">Score Band</span>
          <span className="atlas-conviction-info-box__value">{bandLabel}</span>
        </div>
        <div className="atlas-conviction-info-box" data-testid="conviction-size-range">
          <span className="atlas-conviction-info-box__label">Target Size</span>
          <span className="atlas-conviction-info-box__value">{sizeLabel}</span>
        </div>
      </div>

      {/* ── Section 3: Position details panel ────────────────────────────── */}
      <div className="atlas-conviction-position-panel" data-testid="conviction-position-panel">
        <div className="atlas-conviction-position-row">
          <span className="atlas-conviction-position-row__label">Current Weight</span>
          <span className="atlas-conviction-position-row__value">{data.current_weight_pct.toFixed(2)}%</span>
        </div>
        <div className="atlas-conviction-position-row">
          <span className="atlas-conviction-position-row__label">Size Status</span>
          <span className="atlas-conviction-position-row__value">{SIZE_STATUS_LABEL[data.position_size_status] ?? data.position_size_status}</span>
        </div>
        <div className="atlas-conviction-position-row">
          <span className="atlas-conviction-position-row__label">Room to Add</span>
          <span className="atlas-conviction-position-row__value">{data.room_to_add_pct.toFixed(2)}%</span>
        </div>
        <div className="atlas-conviction-position-row">
          <span className="atlas-conviction-position-row__label">Adds Permitted</span>
          <span
            className={cn(
              'atlas-conviction-position-row__value',
              data.adds_permitted ? 'is-green' : 'is-red',
            )}
            data-testid="conviction-adds-permitted"
          >
            {data.adds_permitted ? 'YES' : 'NO'}
          </span>
        </div>
        {!data.adds_permitted && data.adds_blocked_reason !== null && (
          <p className="atlas-conviction-blocked-reason" data-testid="conviction-blocked-reason">
            {data.adds_blocked_reason}
          </p>
        )}
      </div>

      {/* ── Section 4: Consensus panel (GREY_ZONE only) ───────────────────── */}
      {data.consensus_required && (
        <div className="atlas-conviction-consensus-panel" data-testid="conviction-consensus-panel">
          <p className="atlas-conviction-consensus-panel__title">3-AI Consensus Required</p>
          <div className="atlas-conviction-consensus-panel__status">
            <span className="atlas-conviction-consensus-panel__label">Status</span>
            <span
              className={cn(
                'atlas-conviction-consensus-panel__chip',
                data.consensus_status === 'CONFIRMED' ? 'is-green' : '',
                data.consensus_status === 'FAILED' ? 'is-red' : '',
                data.consensus_status === 'PENDING' ? 'is-amber' : '',
              )}
              data-testid="conviction-consensus-status"
            >
              {CONSENSUS_STATUS_LABEL[data.consensus_status] ?? data.consensus_status}
            </span>
          </div>
        </div>
      )}

      {/* ── Section 5: Cluster panel ──────────────────────────────────────── */}
      <div className="atlas-conviction-cluster-panel" data-testid="conviction-cluster-panel">
        <div className="atlas-conviction-position-row">
          <span className="atlas-conviction-position-row__label">Cluster</span>
          <span className="atlas-conviction-position-row__value">{data.cluster}</span>
        </div>
        <div className="atlas-conviction-position-row">
          <span className="atlas-conviction-position-row__label">Cluster Weight</span>
          <span className="atlas-conviction-position-row__value">{data.cluster_weight_pct.toFixed(2)}%</span>
        </div>
        <div className="atlas-conviction-position-row">
          <span className="atlas-conviction-position-row__label">Cluster Status</span>
          <span className="atlas-conviction-position-row__value">{data.cluster_status}</span>
        </div>
      </div>

      {/* ── Section 6: LEAPS chip (TIER_1_CORE only) ────────────────────── */}
      {data.leaps_eligible && (
        <div className="atlas-conviction-leaps-chip" data-testid="conviction-leaps-chip">
          LEAPS ELIGIBLE
        </div>
      )}

      {/* ── Section 7: Exit counter (WATCHLIST only) ─────────────────────── */}
      {data.tier === 'WATCHLIST' && (
        <div className="atlas-conviction-exit-counter" data-testid="conviction-exit-counter">
          <p className="atlas-conviction-exit-counter__label">
            Exit Cycle: {data.exit_cycle_count} / {EXIT_CYCLE_TRIGGER}
          </p>
          <div className="atlas-conviction-exit-bar">
            <div
              className={cn('atlas-conviction-exit-fill', data.exit_triggered ? 'is-triggered' : '')}
              style={{ width: `${Math.min(100, (data.exit_cycle_count / EXIT_CYCLE_TRIGGER) * 100)}%` }}
            />
          </div>
          {data.exit_triggered && (
            <p className="atlas-conviction-exit-alert" data-testid="conviction-exit-alert">
              Exit triggered — delegate to Framework 16
            </p>
          )}
        </div>
      )}

      {/* ── Section 8: Rationale ─────────────────────────────────────────── */}
      <p className="atlas-conviction-rationale" data-testid="conviction-rationale">
        {bottomMessage}
      </p>
    </div>
  );
}

