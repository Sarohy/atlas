'use client';

import { cn } from '@/lib/utils';
import { useFramework14 } from '@/lib/hooks/use-framework14';
import type { ClusterStatus, ConcentrationStatus, Framework14Result } from '@/lib/schemas/framework14';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Maximum position weight used for weight bar scaling (20% of NAV). */
const BAR_SCALE_MAX = 0.20;

/** Soft cap threshold displayed as a percentage. */
const SOFT_CAP_PCT = 8;

/** Hard review threshold displayed as a percentage. */
const HARD_REVIEW_PCT = 10;

/** CSS chip tone classes by concentration status. */
const CONC_CHIP_TONE: Record<ConcentrationStatus, string> = {
  NORMAL: 'is-f14-grey',
  SOFT_CAP: 'is-f14-amber',
  HARD_REVIEW: 'is-f14-red',
  GRANDFATHERED: 'is-f14-blue',
};

/** Label for each concentration status. */
const CONC_CHIP_LABEL: Record<ConcentrationStatus, string> = {
  NORMAL: 'NORMAL',
  SOFT_CAP: 'SOFT CAP',
  HARD_REVIEW: 'HARD REVIEW',
  GRANDFATHERED: 'GRANDFATHERED',
};

/** CSS fill tone classes for weight bar by concentration status. */
const BAR_FILL_TONE: Record<ConcentrationStatus, string> = {
  NORMAL: '',
  SOFT_CAP: 'is-f14-amber',
  HARD_REVIEW: 'is-f14-red',
  GRANDFATHERED: 'is-f14-blue',
};

/** CSS chip tone for cluster status. */
const CLUSTER_CHIP_TONE: Record<ClusterStatus, string> = {
  NORMAL: 'is-f14-normal',
  YELLOW_ZONE: 'is-f14-yellow',
  RED_ZONE: 'is-f14-red',
};

/** CSS fill tone for cluster bar. */
const CLUSTER_BAR_TONE: Record<ClusterStatus, string> = {
  NORMAL: '',
  YELLOW_ZONE: 'is-f14-yellow',
  RED_ZONE: 'is-f14-red',
};

/** Human-readable sizing tier labels. */
const TIER_LABEL: Record<string, string> = {
  CORE_ANCHOR: 'Core Anchor',
  HIGH_CONVICTION_T2: 'High Conviction T2',
  STANDARD_T2: 'Standard T2',
  T3_SATELLITE: 'T3 Satellite',
  CHINA_RISK: 'China Risk',
  HIGH_BETA: 'High Beta',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtPct(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

function fmtTargetRange(min: number, max: number): string {
  return `${fmtPct(min * 100, 1)} – ${fmtPct(max * 100, 1)} NAV`;
}

function barWidth(pct: number, maxFraction: number): string {
  const capped = Math.min(pct / 100, maxFraction) / maxFraction;
  return `${(capped * 100).toFixed(2)}%`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

type AlertsProps = {
  data: Framework14Result;
};

function Alerts({ data }: AlertsProps) {
  const items: { tone: string; icon: string; message: string }[] = [];

  if (data.grandfathered_expiry_near && data.grandfathered_expires_at !== null) {
    items.push({
      tone: 'is-f14-amber',
      icon: '⚠',
      message: `Grandfathered expiry near — approaches ${fmtPct(data.grandfathered_expires_at * 100)} threshold.`,
    });
  }
  if (data.cluster_status === 'RED_ZONE') {
    items.push({
      tone: 'is-f14-red',
      icon: '🔴',
      message: `${data.cluster} cluster in red zone — ${fmtPct(data.cluster_weight_pct)} of NAV (limit ${fmtPct(data.cluster_red_threshold * 100)}).`,
    });
  }
  if (data.hard_review_triggered && !data.grandfathered) {
    items.push({
      tone: 'is-f14-orange',
      icon: '⚡',
      message: `Hard review threshold breached — position is ${fmtPct(data.position_weight_pct)} of NAV. Trim review recommended.`,
    });
  }

  if (items.length === 0) return null;

  return (
    <div className="atlas-f14-alerts" data-testid="f14-alerts">
      {items.map((item, i) => (
        <div key={i} className={cn('atlas-f14-alert', item.tone)}>
          <span className="atlas-f14-alert-icon" aria-hidden="true">
            {item.icon}
          </span>
          <span>{item.message}</span>
        </div>
      ))}
    </div>
  );
}

type StatRowProps = {
  data: Framework14Result;
};

function StatRow({ data }: StatRowProps) {
  const weightTone = data.soft_cap_breached
    ? data.grandfathered
      ? 'is-f14-blue'
      : 'is-f14-red'
    : '';

  return (
    <div className="atlas-f14-stats-row" data-testid="f14-stats-row">
      <div className="atlas-f14-stat-cell">
        <span className="atlas-f14-stat-label">Position</span>
        <span className={cn('atlas-f14-stat-value', weightTone)} data-testid="f14-stat-weight">
          {fmtPct(data.position_weight_pct)}
        </span>
      </div>
      <div className="atlas-f14-stat-cell">
        <span className="atlas-f14-stat-label">Cluster</span>
        <span className="atlas-f14-stat-value" data-testid="f14-stat-cluster-weight">
          {fmtPct(data.cluster_weight_pct)}
        </span>
      </div>
      <div className="atlas-f14-stat-cell">
        <span className="atlas-f14-stat-label">Adds</span>
        <span
          className={cn(
            'atlas-f14-stat-value',
            data.adds_permitted ? 'is-f14-green' : 'is-f14-red',
          )}
          data-testid="f14-stat-adds"
        >
          {data.adds_permitted ? 'YES' : 'NO'}
        </span>
      </div>
      <div className="atlas-f14-stat-cell">
        <span className="atlas-f14-stat-label">Score Cap</span>
        <span
          className={cn('atlas-f14-stat-value', data.score_display_cap ? 'is-f14-amber' : '')}
          data-testid="f14-stat-score-cap"
        >
          {data.score_display_cap !== null ? String(data.score_display_cap) : '—'}
        </span>
      </div>
    </div>
  );
}

type ConcPanelProps = {
  data: Framework14Result;
};

function ConcPanel({ data }: ConcPanelProps) {
  const expiresAtPct =
    data.grandfathered_expires_at !== null
      ? fmtPct(data.grandfathered_expires_at * 100)
      : null;

  return (
    <div className="atlas-f14-conc-panel" data-testid="f14-conc-panel">
      <div className="atlas-f14-conc-header">
        <span className="atlas-f14-conc-title">Concentration Rules</span>
      </div>
      <div className="atlas-f14-conc-row">
        <span className="atlas-f14-conc-label">Soft cap ({SOFT_CAP_PCT}%) breached</span>
        <span
          className={cn('atlas-f14-conc-badge', data.soft_cap_breached ? 'is-no' : 'is-yes')}
          data-testid="f14-soft-cap-badge"
        >
          {data.soft_cap_breached ? 'YES' : 'NO'}
        </span>
      </div>
      <div className="atlas-f14-conc-row">
        <span className="atlas-f14-conc-label">Hard review ({HARD_REVIEW_PCT}%) triggered</span>
        <span
          className={cn('atlas-f14-conc-badge', data.hard_review_triggered ? 'is-no' : 'is-yes')}
          data-testid="f14-hard-review-badge"
        >
          {data.hard_review_triggered ? 'YES' : 'NO'}
        </span>
      </div>
      {data.grandfathered && (
        <div className="atlas-f14-conc-row">
          <span className="atlas-f14-conc-label">Grandfathered — expires at</span>
          <span className="atlas-f14-conc-badge is-neutral" data-testid="f14-expires-at">
            {expiresAtPct ?? '—'}
          </span>
        </div>
      )}
      <div className="atlas-f14-conc-row">
        <span className="atlas-f14-conc-label">Trim recommended</span>
        <span
          className={cn('atlas-f14-conc-badge', data.trim_recommended ? 'is-no' : 'is-yes')}
          data-testid="f14-trim-badge"
        >
          {data.trim_recommended ? 'YES' : 'NO'}
        </span>
      </div>
    </div>
  );
}

type WeightBarProps = {
  data: Framework14Result;
};

function WeightBar({ data }: WeightBarProps) {
  const fillTone = BAR_FILL_TONE[data.concentration_status];
  const width = barWidth(data.position_weight_pct, BAR_SCALE_MAX);

  return (
    <div className="atlas-f14-weight-bar-section" data-testid="f14-weight-bar">
      <div className="atlas-f14-weight-bar-header">
        <span className="atlas-f14-weight-bar-label">Position weight vs NAV</span>
        <span className="atlas-f14-weight-bar-pct">{fmtPct(data.position_weight_pct)}</span>
      </div>
      <div className="atlas-f14-weight-bar-track" aria-label="Position weight bar">
        <div
          className={cn('atlas-f14-weight-bar-fill', fillTone)}
          style={{ width }}
          data-testid="f14-weight-bar-fill"
        />
      </div>
    </div>
  );
}

type ClusterPanelProps = {
  data: Framework14Result;
};

function ClusterPanel({ data }: ClusterPanelProps) {
  const chipTone = CLUSTER_CHIP_TONE[data.cluster_status];
  const barTone = CLUSTER_BAR_TONE[data.cluster_status];
  const clusterBarWidth = barWidth(data.cluster_weight_pct, data.cluster_red_threshold * 100 * 1.2 / 100);

  return (
    <div className="atlas-f14-cluster-panel" data-testid="f14-cluster-panel">
      <div className="atlas-f14-cluster-header">
        <span className="atlas-f14-cluster-title">Cluster Exposure</span>
        <span
          className={cn('atlas-f14-cluster-status-chip', chipTone)}
          data-testid="f14-cluster-status-chip"
        >
          {data.cluster_status.replace('_', ' ')}
        </span>
      </div>
      <div className="atlas-f14-cluster-name" data-testid="f14-cluster-name">
        {data.cluster}
      </div>
      <div className="atlas-f14-conc-row">
        <span className="atlas-f14-conc-label">Cluster weight</span>
        <span className="atlas-f14-stat-value" data-testid="f14-cluster-pct">
          {fmtPct(data.cluster_weight_pct)}
        </span>
      </div>
      <div className="atlas-f14-conc-row">
        <span className="atlas-f14-conc-label">Yellow zone threshold</span>
        <span className="atlas-f14-stat-value">{fmtPct(data.cluster_yellow_threshold * 100)}</span>
      </div>
      <div className="atlas-f14-conc-row">
        <span className="atlas-f14-conc-label">Red zone threshold</span>
        <span className="atlas-f14-stat-value">{fmtPct(data.cluster_red_threshold * 100)}</span>
      </div>
      <div className="atlas-f14-cluster-bar-track" aria-label="Cluster weight bar">
        <div
          className={cn('atlas-f14-cluster-bar-fill', barTone)}
          style={{ width: clusterBarWidth }}
          data-testid="f14-cluster-bar-fill"
        />
      </div>
    </div>
  );
}

type GuidanceBoxProps = {
  data: Framework14Result;
};

function GuidanceBox({ data }: GuidanceBoxProps) {
  const tierLabel = TIER_LABEL[data.sizing_tier] ?? data.sizing_tier;

  return (
    <div className="atlas-f14-guidance-box" data-testid="f14-guidance-box">
      <div className="atlas-f14-guidance-title">Sizing Guidance</div>
      <div className="atlas-f14-guidance-tier" data-testid="f14-sizing-tier">
        {tierLabel}
      </div>
      <div className="atlas-f14-guidance-range" data-testid="f14-target-range">
        Target: {fmtTargetRange(data.target_weight_min, data.target_weight_max)}
      </div>
      <div className="atlas-f14-guidance-msg" data-testid="f14-message">
        {data.message}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Prop types
// ---------------------------------------------------------------------------

type Framework14CardProps = {
  /** Active ticker driven by the global framework ticker selector. */
  ticker: string;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 14 — Position Sizing Rules card.
 *
 * Sections:
 *   1. Header with concentration status chip
 *   2. 4-stat row (position weight, cluster weight, adds, score cap)
 *   3. Alert stack (expiry near, red zone, hard review)
 *   4. Concentration status panel
 *   5. Weight visualisation bar
 *   6. Cluster panel
 *   7. Sizing guidance box
 */
export function Framework14Card({ ticker }: Framework14CardProps) {
  const { data, isLoading, isError, error } = useFramework14(ticker);
  const hasData = ticker.trim().length > 0 && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load sizing rules.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-f14-panel"
      data-testid="framework14-card"
    >
      {/* ── Header ── */}
      <header className="atlas-f14-header">
        <div className="atlas-f14-header-left">
          <h2 className="atlas-frameworks-panel-title">Framework 14</h2>
          <span className="atlas-fws-subtitle">Position Sizing Rules</span>
        </div>
        {hasData && (
          <span
            className={cn('atlas-f14-chip', CONC_CHIP_TONE[data.concentration_status])}
            data-testid="f14-status-chip"
          >
            {CONC_CHIP_LABEL[data.concentration_status]}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="f14-loading">
            Loading…
          </p>
        )}

        {isError && (
          <p className="atlas-fws-state-msg atlas-fws-state-msg--error" data-testid="f14-error">
            {errorMsg}
          </p>
        )}

        {hasData && (
          <>
            <StatRow data={data} />
            <Alerts data={data} />
            <ConcPanel data={data} />
            <WeightBar data={data} />
            <ClusterPanel data={data} />
            <GuidanceBox data={data} />
          </>
        )}

        {!isLoading && !isError && !hasData && (
          <p className="atlas-fws-state-msg" data-testid="f14-empty">
            Enter a ticker to load position sizing rules.
          </p>
        )}
      </div>
    </section>
  );
}
