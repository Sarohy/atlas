'use client';

import { cn } from '@/lib/utils';
import { useFramework8 } from '@/lib/hooks/use-framework8';
import type { Framework8Response } from '@/lib/schemas/framework8';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Maximum buying bonus the backend can return. */
const MAX_BUYING_BONUS = 5; // matches backend _MAX_BUYING_BONUS

/** Source labels. */
const SOURCE_LABEL: Record<string, string> = {
  sec_edgar: 'SEC EDGAR live',
  default: 'Default (safe)',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resolveChipTone(data: Framework8Response): string {
  if (data.clustered_selling_note != null) return 'is-f8-red';
  if (data.buying_bonus > 0) return 'is-f8-green';
  return 'is-f8-grey';
}

function resolveChipLabel(data: Framework8Response): string {
  if (data.clustered_selling_note != null) return 'CLUSTERED SELLING';
  if (data.buying_bonus > 0) return 'BUYING DETECTED';
  return 'NO SIGNAL';
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
 * Framework 8 — Insider Buying Detector card.
 *
 * Displays whether a ticker has insider buying activity, including:
 * - Status chip (NO SIGNAL / BUYING DETECTED / CLUSTERED SELLING)
 * - Source and buying bonus stat row
 * - Clustered C-suite selling warning (when applicable)
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
          <span className="atlas-fws-subtitle">Insider Buying Detector</span>
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
          label="Buying bonus"
          value={`+${data.buying_bonus} / ${MAX_BUYING_BONUS}`}
          tone={data.buying_bonus > 0 ? 'is-f8-green' : undefined}
        />
      </div>

      {/* ── Main action text ── */}
      <p
        className={cn('atlas-f8-action-text', chipTone)}
        data-testid="f8-action-text"
      >
        {data.clustered_selling_note != null
          ? 'C-SUITE CLUSTERED SELLING DETECTED'
          : data.buying_bonus > 0
            ? `INSIDER BUYING: +${data.buying_bonus} BONUS PTS`
            : 'NO INSIDER SIGNAL'}
      </p>

      {/* ── Clustered selling warning ── */}
      {data.clustered_selling_note != null && (
        <div className="atlas-f8-rule-box is-f8-red" data-testid="f8-clustered-selling-box">
          <p className="atlas-f8-rule-text">
            <strong>Clustered C-suite selling detected.</strong> {data.clustered_selling_note}
          </p>
        </div>
      )}

      {/* ── Buying bonus box ── */}
      {data.buying_bonus > 0 && (
        <div className="atlas-f8-rule-box is-f8-green" data-testid="f8-buying-bonus-box">
          <p className="atlas-f8-rule-text">
            <strong>Insider buying confirms conviction.</strong> {data.buying_bonus} purchase
            {data.buying_bonus !== 1 ? 's' : ''} (Form 4 P/A codes) detected in the last 90 days.
            Each purchase adds 1 point (max +{MAX_BUYING_BONUS}) to the framework total score.
          </p>
        </div>
      )}
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


