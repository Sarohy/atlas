'use client';

import { cn } from '@/lib/utils';
import { useLeaps } from '@/lib/hooks/use-leaps';
import type {
  EntryConditionStatus,
  IVAlert,
  LeapsEligibility,
} from '@/lib/schemas/leaps';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** IV alert chip labels. */
const IV_ALERT_LABEL: Record<IVAlert, string> = {
  NONE: 'IV Normal',
  IV_HIGH_ALERT: 'IV HIGH — BLOCKED',
  IV_COMPRESSION_SIGNAL: 'IV Compression Signal',
  IV_EARNINGS_PROXIMITY: 'IV Earnings Proximity',
  DATA_UNAVAILABLE: 'IV Data Unavailable',
};

/** IV alert chip CSS classes. */
const IV_ALERT_CLASS: Record<IVAlert, string> = {
  NONE: 'is-leaps-iv-none',
  IV_HIGH_ALERT: 'is-leaps-iv-blocked',
  IV_COMPRESSION_SIGNAL: 'is-leaps-iv-signal',
  IV_EARNINGS_PROXIMITY: 'is-leaps-iv-proximity',
  DATA_UNAVAILABLE: 'is-leaps-iv-unknown',
};

/** Entry condition status chip labels. */
const CONDITION_STATUS_LABEL: Record<EntryConditionStatus, string> = {
  CONFIRMED: 'MET',
  NOT_MET: 'NOT MET',
  INCOMPLETE: 'INCOMPLETE',
  NOT_APPLICABLE: 'N/A',
};

/** Entry condition status chip CSS classes. */
const CONDITION_STATUS_CLASS: Record<EntryConditionStatus, string> = {
  CONFIRMED: 'is-leaps-cond-confirmed',
  NOT_MET: 'is-leaps-cond-not-met',
  INCOMPLETE: 'is-leaps-cond-incomplete',
  NOT_APPLICABLE: 'is-leaps-cond-na',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatPct(val: number | null): string {
  if (val === null) return '—';
  return `${(val * 100).toFixed(1)}%`;
}

function formatUsd(val: number | null): string {
  if (val === null) return '—';
  if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
  return `$${val.toFixed(0)}`;
}

/** Tristate eligibility chip class. */
function eligibilityChipClass(eligible: boolean | null, undetermined: boolean): string {
  if (undetermined || eligible === null) return 'is-leaps-elig-unknown';
  return eligible ? 'is-leaps-elig-eligible' : 'is-leaps-elig-blocked';
}

/** Tristate eligibility chip label. */
function eligibilityLabel(eligible: boolean | null, undetermined: boolean): string {
  if (undetermined) return 'INDETERMINATE';
  if (eligible === null) return 'UNKNOWN';
  return eligible ? 'LEAPS ELIGIBLE' : 'LEAPS BLOCKED';
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type LeapsCardProps = {
  /** Active ticker driven by the shared ticker selector. */
  ticker: string;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * LEAPS Strategy card (Section 17).
 *
 * Per-ticker. Sections:
 *   1. Header + eligibility chip
 *   2. Eligibility panel (tristate: ELIGIBLE / BLOCKED / UNKNOWN / INDETERMINATE)
 *   3. Gate checks row (F7 / F29 / F30)
 *   4. Three entry condition cards
 *   5. IV panel
 *   6. Block reasons (if any)
 *   7. Warning messages (if any)
 *   8. Data age footer
 */
export function LeapsCard({ ticker }: LeapsCardProps) {
  const hasTicker = ticker.trim().length > 0;
  const { data, isLoading, isError, error } = useLeaps(ticker);
  const errorMsg =
    error instanceof Error ? error.message : 'Failed to load LEAPS eligibility data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-leaps-panel"
      data-testid="leaps-card"
    >
      {/* ── Section 1: Header + eligibility chip ── */}
      <header className="atlas-leaps-header">
        <div className="atlas-leaps-header-left">
          <h2 className="atlas-frameworks-panel-title">Section 17</h2>
          <span className="atlas-fws-subtitle">LEAPS Strategy</span>
        </div>
        {hasTicker && data !== undefined && (
          <span
            className={cn(
              'atlas-leaps-eligibility-chip',
              eligibilityChipClass(data.leaps_eligible, data.eligibility_undetermined),
            )}
            data-testid="leaps-eligibility-chip"
          >
            {eligibilityLabel(data.leaps_eligible, data.eligibility_undetermined)}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {!hasTicker && (
          <p className="atlas-fws-state-msg" data-testid="leaps-no-ticker">
            Select a ticker to view LEAPS eligibility.
          </p>
        )}

        {hasTicker && isLoading && (
          <p className="atlas-fws-state-msg" data-testid="leaps-loading">
            Loading LEAPS eligibility…
          </p>
        )}

        {hasTicker && isError && (
          <p
            className="atlas-fws-state-msg atlas-fws-state-msg--error"
            data-testid="leaps-error"
          >
            {errorMsg}
          </p>
        )}

        {hasTicker && !isLoading && !isError && data !== undefined && (
          <LeapsContent data={data} />
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Content sub-component
// ---------------------------------------------------------------------------

function LeapsContent({ data }: { data: LeapsEligibility }) {
  return (
    <div className="atlas-leaps-content" data-testid="leaps-content">
      {/* ── Section 2: Score + tier context ── */}
      <div className="atlas-leaps-context-row" data-testid="leaps-context">
        <div className="atlas-leaps-context-cell">
          <span className="atlas-leaps-context-label">Score</span>
          <span className="atlas-leaps-context-value">
            {data.score !== null ? data.score.toFixed(0) : '—'}
          </span>
        </div>
        <div className="atlas-leaps-context-cell">
          <span className="atlas-leaps-context-label">Tier</span>
          <span className="atlas-leaps-context-value">{data.tier ?? '—'}</span>
        </div>
        <div className="atlas-leaps-context-cell">
          <span className="atlas-leaps-context-label">Regime</span>
          <span className="atlas-leaps-context-value">{data.regime_state ?? '—'}</span>
        </div>
        <div className="atlas-leaps-context-cell">
          <span className="atlas-leaps-context-label">Dark Pool Flow</span>
          <span className="atlas-leaps-context-value">
            {data.flow_confirmed === null
              ? '—'
              : data.flow_confirmed
                ? 'CONFIRMED'
                : 'NOT MET'}
          </span>
        </div>
      </div>

      {/* ── Section 3: Gate checks ── */}
      <div className="atlas-leaps-gates-row" data-testid="leaps-gates">
        <GateCell label="F7 Gate" passed={data.gate_f7_active} />
        <GateCell label="F29 Gate" passed={data.gate_f29_passed} />
        <GateCell label="F30 Permits" passed={data.gate_f30_permits_leaps} />
      </div>

      {/* ── Section 4: Entry condition cards ── */}
      <div className="atlas-leaps-conditions" data-testid="leaps-conditions">
        <div className="atlas-leaps-conditions-header">
          <span className="atlas-leaps-conditions-title">Entry Conditions</span>
          <span className="atlas-leaps-conditions-count">
            {data.conditions_met} / {data.conditions_required} met
          </span>
        </div>
        {data.entry_conditions.map((cond, idx) => (
          <div
            key={idx}
            className={cn(
              'atlas-leaps-condition-card',
              CONDITION_STATUS_CLASS[cond.status],
            )}
            data-testid={`leaps-condition-${idx}`}
          >
            <div className="atlas-leaps-condition-header">
              <span className="atlas-leaps-condition-name">{cond.condition_name}</span>
              <span className={cn('atlas-leaps-condition-chip', CONDITION_STATUS_CLASS[cond.status])}>
                {CONDITION_STATUS_LABEL[cond.status]}
              </span>
            </div>
            {cond.detail && (
              <p className="atlas-leaps-condition-detail">{cond.detail}</p>
            )}
          </div>
        ))}
      </div>

      {/* ── Section 5: IV panel ── */}
      <div className="atlas-leaps-iv-panel" data-testid="leaps-iv">
        <div className="atlas-leaps-iv-header">
          <span className="atlas-leaps-iv-title">Implied Volatility</span>
          <span className={cn('atlas-leaps-iv-chip', IV_ALERT_CLASS[data.iv_alert])}>
            {IV_ALERT_LABEL[data.iv_alert]}
          </span>
        </div>
        <div className="atlas-leaps-iv-stats">
          <div className="atlas-leaps-iv-cell">
            <span className="atlas-leaps-iv-label">Current IV</span>
            <span className="atlas-leaps-iv-value">{formatPct(data.iv_current)}</span>
          </div>
          <div className="atlas-leaps-iv-cell">
            <span className="atlas-leaps-iv-label">IV Percentile</span>
            <span className="atlas-leaps-iv-value">{formatPct(data.iv_percentile)}</span>
          </div>
          <div className="atlas-leaps-iv-cell">
            <span className="atlas-leaps-iv-label">IV Blocked</span>
            <span
              className={cn(
                'atlas-leaps-iv-value',
                data.iv_blocked === null
                  ? ''
                  : data.iv_blocked
                    ? 'is-leaps-iv-blocked'
                    : 'is-leaps-iv-none',
              )}
            >
              {data.iv_blocked === null ? '—' : data.iv_blocked ? 'YES' : 'NO'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Section 6: Block reasons ── */}
      {data.block_reasons.length > 0 && (
        <ul className="atlas-leaps-block-reasons" data-testid="leaps-block-reasons">
          {data.block_reasons.map((reason, idx) => (
            <li key={idx} className="atlas-leaps-block-reason">
              {reason}
            </li>
          ))}
        </ul>
      )}

      {/* ── Section 7: Warning messages ── */}
      {data.warning_messages.length > 0 && (
        <ul className="atlas-leaps-warnings" data-testid="leaps-warnings">
          {data.warning_messages.map((msg, idx) => (
            <li key={idx} className="atlas-leaps-warning-item">
              {msg}
            </li>
          ))}
        </ul>
      )}

      {/* ── Section 8: Data age footer ── */}
      <p className="atlas-leaps-footer" data-testid="leaps-footer">
        {data.cache_hit ? 'cached' : 'live'} · {data.data_age_minutes.toFixed(0)} min ago
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gate cell helper
// ---------------------------------------------------------------------------

function GateCell({
  label,
  passed,
}: {
  label: string;
  passed: boolean | null;
}) {
  const cls =
    passed === null
      ? 'is-leaps-gate-unknown'
      : passed
        ? 'is-leaps-gate-passed'
        : 'is-leaps-gate-failed';
  const val = passed === null ? '—' : passed ? 'PASS' : 'FAIL';

  return (
    <div className={cn('atlas-leaps-gate-cell', cls)}>
      <span className="atlas-leaps-gate-label">{label}</span>
      <span className="atlas-leaps-gate-value">{val}</span>
    </div>
  );
}
