'use client';

import { cn } from '@/lib/utils';
import { useFramework13 } from '@/lib/hooks/use-framework13';
import type { Framework13Result } from '@/lib/schemas/framework13';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** AAOI beta threshold — beta >= 3.0 triggers special display. */
const AAOI_BETA_THRESHOLD = 3.0;

/** Status chip labels by warning_level. */
const STATUS_CHIP_LABEL: Record<string, string> = {
  NONE: 'NORMAL',
  AMBER: 'CAUTION',
  RED: 'CAPPED',
  CRITICAL: 'CRITICAL',
};

/** CSS chip tone by warning_level. */
const STATUS_CHIP_TONE: Record<string, string> = {
  NONE: 'is-f13-grey',
  AMBER: 'is-f13-amber',
  RED: 'is-f13-red',
  CRITICAL: 'is-f13-critical',
};

/** Human-readable sizing tier labels. */
const TIER_LABEL: Record<string, string> = {
  CHINA_RISK: 'China Risk',
  AAOI_TYPE_HIGH_BETA: 'AAOI-type High Beta (≥3.0)',
  VERY_HIGH_BETA: 'Very High Beta (≥2.0)',
  HIGH_BETA: 'High Beta (1.5-2.0)',
  MODERATE_BETA: 'Moderate Beta (≥1.0)',
  LOW_BETA: 'Low Beta (<1.0)',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtBeta(value: number): string {
  return value.toFixed(2);
}

function fmtPct(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

function betaBarWidth(positionWeightPct: number, maxPct: number): string {
  const maxFraction = maxPct / 100; // already %, normalise
  const posFraction = positionWeightPct / 100;
  const capped = Math.min(posFraction, maxFraction * 1.2) / (maxFraction * 1.2);
  return `${(capped * 100).toFixed(2)}%`;
}

function capMarkerLeft(maxPct: number): string {
  const maxFraction = maxPct / 100;
  const capped = Math.min(maxFraction, maxFraction * 1.2) / (maxFraction * 1.2);
  return `${(capped * 100).toFixed(2)}%`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

type StatRowProps = {
  data: Framework13Result;
};

function StatRow({ data }: StatRowProps) {
  const betaTone =
    data.beta >= AAOI_BETA_THRESHOLD ? 'is-f13-red' : data.beta >= 2.0 ? 'is-f13-amber' : '';

  const addsTone = data.adds_permitted ? 'is-f13-green' : 'is-f13-red';

  return (
    <div className="atlas-f13-stats-row" data-testid="f13-stats-row">
      <div className="atlas-f13-stat-cell">
        <span className="atlas-f13-stat-label">Beta</span>
        <span className={cn('atlas-f13-stat-value', betaTone)} data-testid="f13-stat-beta">
          {fmtBeta(data.beta)}
        </span>
      </div>
      <div className="atlas-f13-stat-cell">
        <span className="atlas-f13-stat-label">Eff. Exposure</span>
        <span
          className={cn('atlas-f13-stat-value', data.beta_cap_active ? 'is-f13-red' : '')}
          data-testid="f13-stat-eff-exp"
        >
          {fmtPct(data.effective_exposure_pct, 2)}
        </span>
      </div>
      <div className="atlas-f13-stat-cell">
        <span className="atlas-f13-stat-label">Max Weight</span>
        <span className="atlas-f13-stat-value" data-testid="f13-stat-max-weight">
          {data.beta_cap_limit_pct !== null ? fmtPct(data.beta_cap_limit_pct, 1) : '—'}
        </span>
      </div>
      <div className="atlas-f13-stat-cell">
        <span className="atlas-f13-stat-label">Adds</span>
        <span className={cn('atlas-f13-stat-value', addsTone)} data-testid="f13-stat-adds">
          {data.adds_permitted ? 'YES' : 'NO'}
        </span>
      </div>
    </div>
  );
}

type BetaBarProps = {
  data: Framework13Result;
};

function BetaBar({ data }: BetaBarProps) {
  if (data.beta_cap_limit_pct === null) return null;

  const fillTone = data.beta_cap_active ? 'is-f13-red' : '';
  const width = betaBarWidth(data.position_weight_pct, data.beta_cap_limit_pct);
  const markerLeft = capMarkerLeft(data.beta_cap_limit_pct);

  return (
    <div className="atlas-f13-bar-section" data-testid="f13-beta-bar">
      <div className="atlas-f13-bar-header">
        <span className="atlas-f13-bar-label">Position vs Beta Cap</span>
        <span className="atlas-f13-bar-pct">
          {fmtPct(data.position_weight_pct)} / {fmtPct(data.beta_cap_limit_pct)}
        </span>
      </div>
      <div className="atlas-f13-bar-track" aria-label="Position vs beta cap bar">
        <div
          className={cn('atlas-f13-bar-fill', fillTone)}
          style={{ width }}
          data-testid="f13-bar-fill"
        />
        <div
          className="atlas-f13-bar-cap-marker"
          style={{ left: markerLeft }}
          aria-label="Beta cap threshold marker"
          data-testid="f13-bar-cap-marker"
        />
      </div>
    </div>
  );
}

type ExposureNoteProps = {
  data: Framework13Result;
};

function ExposureNote({ data }: ExposureNoteProps) {
  return (
    <div className="atlas-f13-exposure-note" data-testid="f13-exposure-note">
      {data.effective_exposure_note}
    </div>
  );
}

type SizingTierPanelProps = {
  data: Framework13Result;
};

function SizingTierPanel({ data }: SizingTierPanelProps) {
  const tierLabel = TIER_LABEL[data.sizing_tier] ?? data.sizing_tier;

  return (
    <div className="atlas-f13-tier-panel" data-testid="f13-tier-panel">
      <span className="atlas-f13-tier-label">Sizing Tier</span>
      <span className="atlas-f13-tier-value" data-testid="f13-sizing-tier">
        {tierLabel}
      </span>
    </div>
  );
}

type AlertsProps = {
  data: Framework13Result;
};

function Alerts({ data }: AlertsProps) {
  const items: { tone: string; icon: string; message: string }[] = [];

  if (data.beta_cap_active && data.beta_cap_reason !== null) {
    items.push({
      tone: 'is-f13-red',
      icon: '🔴',
      message: data.beta_cap_reason,
    });
  }

  if (data.warning_level === 'AMBER' && data.warning_message !== null) {
    items.push({
      tone: 'is-f13-amber',
      icon: '⚠',
      message: data.warning_message,
    });
  }

  if (data.beta_source_flag) {
    items.push({
      tone: 'is-f13-muted',
      icon: 'ℹ',
      message: 'Beta estimated at 1.0 — no confirmed beta in the ATLAS table for this ticker.',
    });
  }

  if (items.length === 0) return null;

  return (
    <div className="atlas-f13-alerts" data-testid="f13-alerts">
      {items.map((item, i) => (
        <div key={i} className={cn('atlas-f13-alert', item.tone)}>
          <span className="atlas-f13-alert-icon" aria-hidden="true">
            {item.icon}
          </span>
          <span>{item.message}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Prop types
// ---------------------------------------------------------------------------

type Framework13CardProps = {
  /** Active ticker driven by the global framework ticker selector. */
  ticker: string;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 13 — Beta-Adjusted Portfolio Management card.
 *
 * Sections:
 *   1. Header with warning status chip (NORMAL / CAUTION / CAPPED / CRITICAL)
 *   2. 4-stat row: beta, effective exposure, max weight, adds permitted
 *   3. Beta exposure bar with cap marker
 *   4. Effective exposure note
 *   5. Sizing tier panel
 *   6. Alert stack (cap active, AAOI amber warning, default beta flag)
 */
export function Framework13Card({ ticker }: Framework13CardProps) {
  const { data, isLoading, isError, error } = useFramework13(ticker);
  const hasData = ticker.trim().length > 0 && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load beta data.';

  const warningLevel = hasData ? data.warning_level : 'NONE';
  const chipLabel = STATUS_CHIP_LABEL[warningLevel] ?? warningLevel;
  const chipTone = STATUS_CHIP_TONE[warningLevel] ?? 'is-f13-grey';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-f13-panel"
      data-testid="framework13-card"
    >
      {/* ── Header ── */}
      <header className="atlas-f13-header">
        <div className="atlas-f13-header-left">
          <h2 className="atlas-frameworks-panel-title">Framework 13</h2>
          <span className="atlas-fws-subtitle">Beta Management</span>
        </div>
        {hasData && (
          <span className={cn('atlas-f13-chip', chipTone)} data-testid="f13-status-chip">
            {chipLabel}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="f13-loading">
            Loading…
          </p>
        )}

        {isError && (
          <p className="atlas-fws-state-msg atlas-fws-state-msg--error" data-testid="f13-error">
            {errorMsg}
          </p>
        )}

        {hasData && (
          <>
            <StatRow data={data} />
            <BetaBar data={data} />
            <ExposureNote data={data} />
            <SizingTierPanel data={data} />
            <Alerts data={data} />
          </>
        )}

        {!isLoading && !isError && !hasData && (
          <p className="atlas-fws-state-msg" data-testid="f13-empty">
            Enter a ticker to load beta data.
          </p>
        )}
      </div>
    </section>
  );
}
