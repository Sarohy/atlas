'use client';

import { cn } from '@/lib/utils';
import { useLeaps } from '@/lib/hooks/use-leaps';
import type { EntryConditionStatus, LeapsEligibility } from '@/lib/schemas/leaps';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** F33 static exclusion list — OTC / foreign / thin US options chains. */
const EXCLUDED_TICKER_MARKER = 'excluded from LEAPS';

/** Condition status chip labels. */
const COND_STATUS_LABEL: Record<EntryConditionStatus, string> = {
  CONFIRMED: 'CONFIRMED',
  NOT_MET: 'NOT MET',
  INCOMPLETE: 'INCOMPLETE',
  NOT_APPLICABLE: 'N/A',
};

/** Condition status chip CSS classes. */
const COND_STATUS_CLASS: Record<EntryConditionStatus, string> = {
  CONFIRMED: 'is-f33-cond-confirmed',
  NOT_MET: 'is-f33-cond-not-met',
  INCOMPLETE: 'is-f33-cond-incomplete',
  NOT_APPLICABLE: 'is-f33-cond-na',
};

// Standard size per F33 spec.
const STANDARD_MAX_PCT = 1.0; // 1.0% per name — no F30 gate
const CARVEOUT_MAX_PCT = 0.5; // 0.5% per name — F30 drawdown gate active
const BASELINE_PCT = 0.3; // 0.3% baseline
const BUCKET_TOTAL_CAP_PCT = 4.0; // 4% NAV hard cap (Bucket 2)
const AND_GATE_THRESHOLD_USD = 10_000; // Entries above this require AND gate

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type Framework33CardProps = {
  /** Active ticker driven by the shared ticker selector. */
  ticker: string;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 33 — LEAPS Entry Conditions V2.
 *
 * Surfaces the three F33 entry gates (A: Calm Accumulation, B: Washout,
 * C: Bull Market Path) and sizing guidance. Data is sourced from the LEAPS
 * eligibility endpoint since F33 conditions are evaluated inside the LEAPS
 * pipeline.
 *
 * Sections:
 *   1. Header + entry-permitted chip
 *   2. Excluded ticker warning (when applicable)
 *   3. Condition A card (Calm Accumulation)
 *   4. Condition B card (Washout)
 *   5. Condition C card (Bull Market Path)
 *   6. Size guidance
 *   7. AND gate note
 *   8. Block reasons (if any)
 *   9. Data age footer
 */
export function Framework33Card({ ticker }: Framework33CardProps) {
  const hasTicker = ticker.trim().length > 0;
  const { data, isLoading, isError, error } = useLeaps(ticker);
  const errorMsg =
    error instanceof Error ? error.message : 'Failed to load F33 entry condition data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-f33-panel"
      data-testid="framework33-card"
    >
      {/* ── Section 1: Header + chip ── */}
      <header className="atlas-f33-header">
        <div className="atlas-f33-header-left">
          <h2 className="atlas-frameworks-panel-title">Framework 33</h2>
          <span className="atlas-fws-subtitle">LEAPS Entry Conditions V2</span>
        </div>
        {hasTicker && data !== undefined && (
          <span
            className={cn('atlas-f33-entry-chip', entryChipClass(data))}
            data-testid="f33-entry-chip"
          >
            {entryChipLabel(data)}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {!hasTicker && (
          <p className="atlas-fws-state-msg" data-testid="f33-no-ticker">
            Select a ticker to view F33 entry conditions.
          </p>
        )}

        {hasTicker && isLoading && (
          <p className="atlas-fws-state-msg" data-testid="f33-loading">
            Loading F33 entry conditions…
          </p>
        )}

        {hasTicker && isError && (
          <p
            className="atlas-fws-state-msg atlas-fws-state-msg--error"
            data-testid="f33-error"
          >
            {errorMsg}
          </p>
        )}

        {hasTicker && !isLoading && !isError && data !== undefined && (
          <F33Content data={data} />
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function entryChipClass(data: LeapsEligibility): string {
  if (data.eligibility_undetermined || data.leaps_eligible === null) return 'is-f33-unknown';
  return data.leaps_eligible ? 'is-f33-permitted' : 'is-f33-blocked';
}

function entryChipLabel(data: LeapsEligibility): string {
  if (data.eligibility_undetermined) return 'INDETERMINATE';
  if (data.leaps_eligible === null) return 'UNKNOWN';
  return data.leaps_eligible ? 'ENTRY PERMITTED' : 'BLOCKED';
}

function isExcluded(data: LeapsEligibility): boolean {
  return data.block_reasons.some((r) => r.includes(EXCLUDED_TICKER_MARKER));
}

/** Derive F33 size guidance from the size_guidance field in the LEAPS response. */
function sizeGuidance(data: LeapsEligibility): {
  maxPct: number;
  baselinePct: number;
  baselineMaxPct: number;
  carveoutActive: boolean;
  dataMissing: boolean;
} {
  const sg = data.size_guidance;
  return {
    maxPct: sg.standard_max_pct,
    baselinePct: sg.baseline_pct,
    baselineMaxPct: sg.baseline_max_pct,
    carveoutActive: sg.carveout_active,
    dataMissing: sg.data_missing,
  };
}

// ---------------------------------------------------------------------------
// Content sub-component
// ---------------------------------------------------------------------------

function F33Content({ data }: { data: LeapsEligibility }) {
  const excluded = isExcluded(data);
  const size = sizeGuidance(data);

  // Extract F33-specific conditions by name prefix.
  const condA = data.entry_conditions.find((c) =>
    c.condition_name.includes('Condition A'),
  );
  const condB = data.entry_conditions.find((c) =>
    c.condition_name.includes('Condition B'),
  );
  const condC = data.entry_conditions.find((c) =>
    c.condition_name.includes('Condition C'),
  );

  return (
    <div className="atlas-f33-content" data-testid="f33-content">
      {/* ── Excluded ticker banner ── */}
      {excluded && (
        <div className="atlas-f33-excluded-banner" data-testid="f33-excluded-chip">
          <span className="atlas-f33-excluded-label">EXCLUDED</span>
          <span className="atlas-f33-excluded-detail">
            OTC / foreign / thin US options chain — not eligible for LEAPS
          </span>
        </div>
      )}

      {/* ── Condition A ── */}
      {!excluded && (
        <div
          className={cn(
            'atlas-f33-condition',
            condA ? COND_STATUS_CLASS[condA.status] : 'is-f33-cond-incomplete',
          )}
          data-testid="f33-condition-a"
        >
          <div className="atlas-f33-condition-header">
            <div className="atlas-f33-condition-title-row">
              <span className="atlas-f33-condition-label">Condition A</span>
              <span className="atlas-f33-condition-name">Calm Accumulation</span>
            </div>
            <span
              className={cn(
                'atlas-f33-condition-chip',
                condA ? COND_STATUS_CLASS[condA.status] : 'is-f33-cond-incomplete',
              )}
              data-testid="f33-condition-a-chip"
            >
              {condA ? COND_STATUS_LABEL[condA.status] : 'INCOMPLETE'}
            </span>
          </div>
          <p className="atlas-f33-condition-rule">
            ≥20% drawdown from high AND VIX 15–18 (calm window)
          </p>
          {condA?.detail && (
            <p className="atlas-f33-condition-detail">{condA.detail}</p>
          )}
        </div>
      )}

      {/* ── Condition B ── */}
      {!excluded && (
        <div
          className={cn(
            'atlas-f33-condition',
            condB ? COND_STATUS_CLASS[condB.status] : 'is-f33-cond-incomplete',
          )}
          data-testid="f33-condition-b"
        >
          <div className="atlas-f33-condition-header">
            <div className="atlas-f33-condition-title-row">
              <span className="atlas-f33-condition-label">Condition B</span>
              <span className="atlas-f33-condition-name">Washout</span>
            </div>
            <span
              className={cn(
                'atlas-f33-condition-chip',
                condB ? COND_STATUS_CLASS[condB.status] : 'is-f33-cond-incomplete',
              )}
              data-testid="f33-condition-b-chip"
            >
              {condB ? COND_STATUS_LABEL[condB.status] : 'INCOMPLETE'}
            </span>
          </div>
          <p className="atlas-f33-condition-rule">
            ≥25% sector drawdown + confirmed cap. volume + VIX elevated but declining
          </p>
          {condB?.detail && (
            <p className="atlas-f33-condition-detail">{condB.detail}</p>
          )}
        </div>
      )}

      {/* ── Condition C ── */}
      {!excluded && (
        <div
          className={cn(
            'atlas-f33-condition',
            condC ? COND_STATUS_CLASS[condC.status] : 'is-f33-cond-incomplete',
          )}
          data-testid="f33-condition-c"
        >
          <div className="atlas-f33-condition-header">
            <div className="atlas-f33-condition-title-row">
              <span className="atlas-f33-condition-label">Condition C</span>
              <span className="atlas-f33-condition-name">Bull Market Path</span>
            </div>
            <span
              className={cn(
                'atlas-f33-condition-chip',
                condC ? COND_STATUS_CLASS[condC.status] : 'is-f33-cond-incomplete',
              )}
              data-testid="f33-condition-c-chip"
            >
              {condC ? COND_STATUS_LABEL[condC.status] : 'INCOMPLETE'}
            </span>
          </div>
          <p className="atlas-f33-condition-rule">
            T1E ≥85 + dark pool bullish + options flow confirmed + no gap day
          </p>
          {condC?.detail && (
            <p className="atlas-f33-condition-detail">{condC.detail}</p>
          )}
        </div>
      )}

      {/* ── Size guidance ── */}
      <div className="atlas-f33-size-guidance" data-testid="f33-size-guidance">
        <span className="atlas-f33-size-title">Per-Name Size</span>
        <div className="atlas-f33-size-row">
          <div className="atlas-f33-size-cell">
            <span className="atlas-f33-size-label">Baseline range</span>
            <span className="atlas-f33-size-value">
              {size.baselinePct.toFixed(1)}–{size.baselineMaxPct.toFixed(2)}%
            </span>
          </div>
          <div className="atlas-f33-size-cell">
            <span className="atlas-f33-size-label">Max per name</span>
            <span
              className={cn(
                'atlas-f33-size-value',
                size.carveoutActive ? 'is-f33-size-carveout' : '',
              )}
            >
              {size.maxPct.toFixed(1)}%
              {size.carveoutActive && (
                <span className="atlas-f33-size-carveout-badge">
                  {size.dataMissing ? ' (F30 unknown)' : ' (F30 carveout)'}
                </span>
              )}
            </span>
          </div>
          <div className="atlas-f33-size-cell">
            <span className="atlas-f33-size-label">Bucket cap</span>
            <span className="atlas-f33-size-value">{BUCKET_TOTAL_CAP_PCT.toFixed(0)}% NAV</span>
          </div>
        </div>
      </div>

      {/* ── AND gate note ── */}
      <div className="atlas-f33-and-gate" data-testid="f33-and-gate-note">
        <span className="atlas-f33-and-gate-icon">⚠</span>
        <span className="atlas-f33-and-gate-text">
          Entries above ${AND_GATE_THRESHOLD_USD.toLocaleString()} require{' '}
          <strong>AND gate</strong> — CLEAR regime + F29 3-of-5 signals
        </span>
      </div>

      {/* ── Block reasons ── */}
      {data.block_reasons.length > 0 && (
        <ul className="atlas-f33-block-reasons" data-testid="f33-block-reasons">
          {data.block_reasons.map((reason, idx) => (
            <li key={idx} className="atlas-f33-block-reason">
              {reason}
            </li>
          ))}
        </ul>
      )}

      {/* ── Footer ── */}
      <p className="atlas-f33-footer" data-testid="f33-footer">
        {data.cache_hit ? 'cached' : 'live'} · {data.data_age_minutes.toFixed(0)} min ago
      </p>
    </div>
  );
}
