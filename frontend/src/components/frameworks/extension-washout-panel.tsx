'use client';

import { cn } from '@/lib/utils';
import { useExtensionWashout } from '@/lib/hooks/use-extension-washout';
import type { ExtensionWashoutResponse, WashoutState } from '@/lib/schemas/extension-washout';

// ---------------------------------------------------------------------------
// Display maps
// ---------------------------------------------------------------------------

const STATE_LABEL: Record<WashoutState, string> = {
  STOP_ADD: 'Stop-Add / No-Chase',
  ARM_PROTECTION: 'Arm Protection',
  ACTIVE_PROTECTION: 'Active Protection',
  HEDGE: 'Hedge',
  TRIM_WATCH: 'Trim-Watch',
  TRIM: 'Trim',
  FORCED_DE_RISK_REVIEW: 'Forced De-Risk Review',
  BOOK_LEVEL_HEDGE: 'Book-Level Hedge',
  WAIT: 'Wait / Data Gap',
};

const STATE_TONE: Record<WashoutState, string> = {
  STOP_ADD: 'is-yellow',
  ARM_PROTECTION: 'is-yellow',
  ACTIVE_PROTECTION: 'is-orange',
  HEDGE: 'is-orange',
  TRIM_WATCH: 'is-orange',
  TRIM: 'is-red',
  FORCED_DE_RISK_REVIEW: 'is-red',
  BOOK_LEVEL_HEDGE: 'is-red',
  WAIT: 'is-muted',
};

const TRACK_LABEL: Record<string, string> = {
  EXTENSION: 'Extension-managed',
  BREADTH_FLOW: 'Breadth/Flow-managed',
};

// Overshoot Elasticity tiers (SPEC v2.1).
const ELASTICITY_LABEL: Record<string, string> = {
  EXTREME: 'Extreme',
  HIGH: 'High',
  MODERATE: 'Moderate',
  LOW: 'Low',
  SHARP_FALLER: 'Sharp-Faller',
  NEVER_CROSS: 'Never-Cross',
  ANOMALY: 'Anomaly',
  UNKNOWN: 'Unknown',
};
const ELASTICITY_TONE: Record<string, string> = {
  EXTREME: 'is-green',
  HIGH: 'is-cyan',
  MODERATE: 'is-yellow',
  LOW: 'is-orange',
  SHARP_FALLER: 'is-red',
  NEVER_CROSS: 'is-orange',
  ANOMALY: 'is-muted',
  UNKNOWN: 'is-muted',
};

// The six §7 behavioural confirmation legs, in checklist order.
const LEG_LABELS: Array<[keyof ExtensionWashoutResponse, string]> = [
  ['flow_distribution', 'Flow → distribution (DP sell ≥ 80%)'],
  ['vwap_lost', 'VWAP lost (closing basis)'],
  ['group_rolling', 'Group rolling together (breadth)'],
  ['absorption', 'Absorption, no follow-through (§4)'],
  ['hard_override', 'Hard override (close < 20d/50d)'],
  ['negative_catalyst', 'Negative catalyst'],
];

function fmtPct(value: number | null | undefined): string {
  if (value == null) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

type ExtensionWashoutPanelProps = {
  ticker: string;
  /** Live position weight (% NAV) for the §3.1 size gate; omit when unknown. */
  positionWeightPct?: number | null;
  /** Beta for the overshoot-elasticity score (SPEC v2.1); omit when unknown. */
  beta?: number | null;
};

/**
 * Extension & Washout Overlay (Spec v2) — a display/posture panel. It never
 * touches the F1-F5 score; it shows WHEN to protect/trim and at what posture
 * via the nine-state model.
 */
export function ExtensionWashoutPanel({
  ticker,
  positionWeightPct,
  beta,
}: ExtensionWashoutPanelProps) {
  const { data, isLoading, isError, error } = useExtensionWashout(
    ticker,
    positionWeightPct,
    false,
    beta,
  );
  const hasData = ticker.trim().length > 0 && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load washout overlay.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel"
      data-testid="extension-washout-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <div>
          <h2 className="atlas-frameworks-panel-title">Extension &amp; Washout</h2>
          <span className="atlas-fws-subtitle">When to protect / trim · posture only</span>
        </div>
        {hasData && (
          <span
            className={cn('atlas-frameworks-pill atlas-fws-action-pill', STATE_TONE[data.state])}
            data-testid="washout-state"
          >
            {STATE_LABEL[data.state]}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && <p className="atlas-fws-state-msg">Computing overlay…</p>}
        {isError && (
          <p className="atlas-fws-state-msg atlas-fws-state-msg--error">{errorMsg}</p>
        )}
        {!isLoading && !isError && hasData && <WashoutContent data={data} />}
        {!isLoading && !isError && !hasData && ticker.trim().length > 0 && (
          <p className="atlas-fws-state-msg">No overlay data for {ticker}.</p>
        )}
      </div>
    </section>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="atlas-fws-calc-row">
      <span className="atlas-fws-calc-label">{label}</span>
      <span className="atlas-fws-calc-value">{value}</span>
    </div>
  );
}

function WashoutContent({ data }: { data: ExtensionWashoutResponse }) {
  return (
    <div data-testid="washout-content">
      <p className="atlas-fws-state-msg" data-testid="washout-reason">
        {data.reason}
      </p>

      {/* Track / overshoot / ladder rung */}
      <div className="atlas-f4-signal-row">
        <span className="atlas-frameworks-pill atlas-f4-tier-pill is-muted" data-testid="washout-track">
          {TRACK_LABEL[data.track] ?? data.track}
        </span>
        <span className="atlas-frameworks-pill atlas-f4-tier-pill is-muted">
          {data.overshoot.replace('_', ' ').toLowerCase()}
        </span>
        {data.low_confidence && (
          <span className="atlas-frameworks-pill atlas-f4-tier-pill is-orange">low-confidence</span>
        )}
      </div>

      <div className="atlas-fws-breakdown-divider" />
      <MetricRow label="Ladder rung" value={data.rung} />
      <MetricRow label="vs 50-day" value={fmtPct(data.dist_50d)} />
      <MetricRow label="RSI 14" value={data.rsi_14 == null ? '—' : data.rsi_14.toFixed(1)} />
      <MetricRow label="21d / 14d / 20d move" value={
        `${fmtPct(data.move_21d_pct)} / ${fmtPct(data.move_14d_pct)} / ${fmtPct(data.move_20d_pct)}`
      } />
      <MetricRow
        label="DP sell% (latest)"
        value={data.dark_pool_sell_pct == null ? '—' : `${data.dark_pool_sell_pct.toFixed(0)}%`}
      />
      {data.metric_legs.extreme.length > 0 && (
        <MetricRow label="Extreme legs" value={data.metric_legs.extreme.join(', ')} />
      )}

      {/* §3.1 position-size gate */}
      <MetricRow
        label="Position vs target"
        value={
          data.position_weight_pct == null
            ? `target ${data.target_pct.toFixed(0)}% (weight n/a)`
            : `${data.position_weight_pct.toFixed(1)}% / ${data.target_pct.toFixed(0)}% ` +
              (data.below_target ? '(below)' : '(at/above)')
        }
      />
      {data.size_relabeled && (
        <p className="atlas-fws-state-msg" data-testid="washout-size-note">
          ⓘ Below target — trim re-labeled to Stop-Add / Pullback-Only (§3.1).
        </p>
      )}

      {/* Overshoot Elasticity (SPEC v2.1) */}
      <div className="atlas-fws-breakdown-divider" />
      <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
        <span className="atlas-fws-calc-label">Overshoot Elasticity (v2.1)</span>
        <span
          className={cn(
            'atlas-frameworks-pill atlas-f4-tier-pill',
            ELASTICITY_TONE[data.elasticity_tier] ?? 'is-muted',
          )}
          data-testid="washout-elasticity-tier"
        >
          {ELASTICITY_LABEL[data.elasticity_tier] ?? data.elasticity_tier}
        </span>
      </div>
      <MetricRow
        label="+40 behavior"
        value={data.plus40_behavior || '—'}
      />
      <MetricRow
        label="Score / confidence"
        value={`${data.elasticity_score ?? '—'} · ${data.elasticity_confidence} (${data.elasticity_event_count} events)`}
      />
      <MetricRow
        label="Trim-rung ladder"
        value={
          data.elasticity_ladder.length === 3
            ? `+${data.elasticity_ladder[0]}/+${data.elasticity_ladder[1]}/+${data.elasticity_ladder[2]}`
            : '—'
        }
      />
      <MetricRow label="RV20 / RV60 / β" value={
        `${data.rv20 == null ? '—' : data.rv20.toFixed(0)}% / ` +
        `${data.rv60 == null ? '—' : data.rv60.toFixed(0)}% / ` +
        `${data.beta == null ? '—' : data.beta.toFixed(2)}`
      } />
      {data.sizing_guidance && (
        <p className="atlas-fws-state-msg" data-testid="washout-sizing">
          {data.sizing_guidance}
        </p>
      )}
      {(data.elasticity_provisional ||
        data.elasticity_watch_promote ||
        data.elasticity_excluded_from_recalibration ||
        data.elasticity_hard_override) && (
        <div className="atlas-f4-signal-row">
          {data.elasticity_hard_override && (
            <span className="atlas-frameworks-pill atlas-f4-tier-pill is-red">hard override</span>
          )}
          {data.elasticity_provisional && (
            <span className="atlas-frameworks-pill atlas-f4-tier-pill is-orange">provisional</span>
          )}
          {data.elasticity_watch_promote && (
            <span className="atlas-frameworks-pill atlas-f4-tier-pill is-yellow">watch-promote</span>
          )}
          {data.elasticity_excluded_from_recalibration && (
            <span className="atlas-frameworks-pill atlas-f4-tier-pill is-muted">
              excl. recalibration
            </span>
          )}
        </div>
      )}
      {data.elasticity_data_gaps.length > 0 && (
        <p className="atlas-fws-state-msg" data-testid="washout-elasticity-gaps">
          DATA GAP (not in elasticity score): {data.elasticity_data_gaps.join(', ')}
        </p>
      )}

      {/* Confirmation legs (§7) */}
      <div className="atlas-fws-breakdown-divider" />
      <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
        <span className="atlas-fws-calc-label">
          Confirmation legs ({data.confirmation_count}/2 to trim)
        </span>
        <span
          className={cn(
            'atlas-frameworks-pill atlas-fws-action-pill',
            data.trim_authorized ? 'is-red' : 'is-muted',
          )}
          data-testid="washout-trim-authorized"
        >
          {data.trim_authorized ? 'TRIM AUTHORIZED' : 'not authorized'}
        </span>
      </div>
      {LEG_LABELS.map(([key, label]) => (
        <MetricRow key={key} label={label} value={data[key] ? '✓' : '—'} />
      ))}

      {/* Breadth (§5) */}
      <div className="atlas-fws-breakdown-divider" />
      <MetricRow
        label={`Breadth (${data.breadth_universe_size}-name)`}
        value={
          (data.breadth ? `${data.breadth.replace('BREADTH_', '')} · ` : 'calm · ') +
          `${data.breadth_watch_count} down ≥5% / ${data.breadth_hedge_count} down ≥7%`
        }
      />
    </div>
  );
}
