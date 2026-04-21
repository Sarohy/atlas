'use client';

import { cn } from '@/lib/utils';
import { useFramework8 } from '@/lib/hooks/use-framework8';
import type { Framework8Response, InsiderTier } from '@/lib/schemas/framework8';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Minimum sale USD below which the amount is shown as "< $1 K". */
const DISPLAY_MIN_USD = 1_000;

/** Threshold above which the card shows "LARGE SALE". */
const LARGE_SALE_THRESHOLD = 1_000_000;

/** Human-readable tier labels. */
const TIER_LABEL: Record<InsiderTier, string> = {
  TIER1: 'Tier 1 — CEO / CFO / COO',
  TIER2: 'Tier 2 — CTO / CPO / CMO',
  TIER3: 'Tier 3 — Director / Officer',
};

/** Source labels. */
const SOURCE_LABEL: Record<string, string> = {
  hardcoded: 'Client-confirmed',
  sec_edgar: 'SEC EDGAR live',
  default: 'Default (safe)',
};

/** CSS tone classes per top-level state. */
const CHIP_TONE = {
  hard_pass: 'is-f8-purple',
  flag_active: 'is-f8-red',
  clear: 'is-f8-green',
} as const;

/** F5 cap badge tones. */
const CAP_TONE: Record<number, string> = {
  68: 'is-f8-orange',
  72: 'is-f8-amber',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatUsd(usd: number): string {
  if (usd >= 1_000_000) return `$${(usd / 1_000_000).toFixed(1)}M`;
  if (usd >= 1_000) return `$${Math.round(usd / 1_000)}K`;
  return `< $${DISPLAY_MIN_USD.toLocaleString()}`;
}

function resolveChipTone(data: Framework8Response): string {
  if (data.hard_pass) return CHIP_TONE.hard_pass;
  if (data.flag_active) return CHIP_TONE.flag_active;
  return CHIP_TONE.clear;
}

function resolveChipLabel(data: Framework8Response): string {
  if (data.hard_pass) return 'HARD PASS';
  if (data.flag_active) return 'FLAG ACTIVE';
  return 'CLEAR';
}

// ---------------------------------------------------------------------------
// Prop types
// ---------------------------------------------------------------------------

type Framework8CardProps = {
  /** Active ticker driven by the global framework ticker selector. */
  ticker: string;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 8 — Insider Activity Flag card.
 *
 * Displays whether a ticker has an active insider-selling flag, including:
 * - Status chip (CLEAR / FLAG ACTIVE / HARD PASS)
 * - Source, filer tier, and F5 cap stat row
 * - Main action text and rule summary
 * - Hard-pass warning box (when applicable)
 * - F5 score impact section
 * - Three-filter pipeline legend
 */
export function Framework8Card({ ticker }: Framework8CardProps) {
  const { data, isLoading, isError, error } = useFramework8(ticker);
  const hasData = ticker.trim().length > 0 && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load insider data.';
  const chipTone = hasData ? resolveChipTone(data) : '';
  const chipLabel = hasData ? resolveChipLabel(data) : '';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-f8-panel"
      data-testid="framework8-card"
    >
      {/* ── Header ── */}
      <header className="atlas-f8-header">
        <div className="atlas-f8-header-left">
          <h2 className="atlas-frameworks-panel-title">Framework 8</h2>
          <span className="atlas-fws-subtitle">Insider Activity Flag</span>
        </div>
        {hasData && (
          <span
            className={cn('atlas-f8-chip', chipTone)}
            data-testid="f8-status-chip"
          >
            {chipLabel}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="f8-loading">
            Checking insider filings…
          </p>
        )}
        {isError && (
          <p className="atlas-fws-state-msg atlas-fws-state-msg--error" data-testid="f8-error">
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && hasData && <InsiderContent data={data} />}
        {!isLoading && !isError && !hasData && ticker.trim().length > 0 && (
          <p className="atlas-fws-state-msg" data-testid="f8-empty">
            No insider data available for {ticker}.
          </p>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main content
// ---------------------------------------------------------------------------

function InsiderContent({ data }: { data: Framework8Response }) {
  const chipTone = resolveChipTone(data);

  return (
    <div className="atlas-f8-content" data-testid="f8-content">
      {/* ── Stat row ── */}
      <div className="atlas-f8-stats-row">
        <StatCell label="Source" value={SOURCE_LABEL[data.source] ?? data.source} />
        <StatCell
          label="Filer tier"
          value={data.filer_tier ? TIER_LABEL[data.filer_tier] : '—'}
          tone={data.filer_tier ? chipTone : undefined}
        />
        <StatCell
          label="Largest sale"
          value={data.largest_sale_usd != null ? formatUsd(data.largest_sale_usd) : '—'}
          tone={
            data.largest_sale_usd != null && data.largest_sale_usd >= LARGE_SALE_THRESHOLD
              ? 'is-f8-orange'
              : undefined
          }
        />
        <StatCell
          label="F5 cap"
          value={data.f5_cap != null ? String(data.f5_cap) : 'none'}
          tone={data.f5_cap != null ? (CAP_TONE[data.f5_cap] ?? 'is-f8-amber') : undefined}
        />
      </div>

      {/* ── Main action text ── */}
      <p
        className={cn('atlas-f8-action-text', chipTone)}
        data-testid="f8-action-text"
      >
        {data.hard_pass
          ? 'REMOVE FROM UNIVERSE'
          : data.flag_active
            ? 'INSIDER FLAG ACTIVE'
            : 'NO INSIDER FLAG'}
      </p>

      {/* ── Hard pass warning ── */}
      {data.hard_pass && <HardPassBox />}

      {/* ── F5 impact ── */}
      {data.flag_active && data.f5_cap != null && <F5ImpactBox cap={data.f5_cap} />}

      {/* ── Rule boxes ── */}
      <RuleSummaryBox data={data} chipTone={chipTone} />

      {/* ── Filter legend ── */}
      <FilterLegend />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="atlas-f8-stat-cell">
      <span className="atlas-f8-stat-label">{label}</span>
      <span className={cn('atlas-f8-stat-value', tone)}>{value}</span>
    </div>
  );
}

function HardPassBox() {
  return (
    <div className="atlas-f8-rule-box is-f8-purple" data-testid="f8-hard-pass-box">
      <p className="atlas-f8-rule-text">
        <strong>Hard pass pattern detected.</strong> Multiple insider sales with zero purchases
        recorded. This ticker should be removed from the investable universe entirely — do not add
        or initiate a position.
      </p>
    </div>
  );
}

function F5ImpactBox({ cap }: { cap: number }) {
  const tone = CAP_TONE[cap] ?? 'is-f8-amber';
  const reason =
    cap === 68
      ? 'Large sale (≥ $1M) or Tier 1 (C-suite) filer — strict cap applies.'
      : 'Standard discretionary sale — moderate cap applies.';

  return (
    <div className={cn('atlas-f8-rule-box', tone)} data-testid="f8-f5-impact-box">
      <p className="atlas-f8-rule-text">
        <strong>F5 score capped at {cap}.</strong> {reason} Framework 5 will not exceed this value
        until the flag clears.
      </p>
    </div>
  );
}

function RuleSummaryBox({
  data,
  chipTone,
}: {
  data: Framework8Response;
  chipTone: string;
}) {
  const message = data.flag_active
    ? `Discretionary insider sale confirmed for ${data.ticker}. The F5 cap is now active and Framework 7 has been notified for the double-block check.`
    : data.source === 'hardcoded'
      ? `${data.ticker} is on the client-confirmed active-flag list. Flag applied directly from human review.`
      : `No discretionary insider sales detected for ${data.ticker} in the last 90 days. Gate open.`;

  return (
    <div className={cn('atlas-f8-rule-box', chipTone)} data-testid="f8-rule-box">
      <p className="atlas-f8-rule-text">{message}</p>
    </div>
  );
}

function FilterLegend() {
  const steps = [
    { label: 'Sponsor?', desc: 'PE / financial sponsor — no cap applied' },
    { label: '10b5-1?', desc: 'Pre-planned trade — excluded' },
    { label: 'Discretionary?', desc: 'Confirmed sale — flag raised' },
  ] as const;

  return (
    <div className="atlas-f8-filter-legend" aria-label="Three-filter pipeline" role="list">
      {steps.map((step, i) => (
        <div className="atlas-f8-filter-step" key={step.label} role="listitem">
          <span className="atlas-f8-filter-label">{step.label}</span>
          <span className="atlas-f8-filter-desc">{step.desc}</span>
          {i < steps.length - 1 && (
            <span aria-hidden="true" className="atlas-f8-filter-arrow">
              →
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
