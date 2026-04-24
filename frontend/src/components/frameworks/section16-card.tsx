'use client';

import { useState } from 'react';

import { cn } from '@/lib/utils';
import { useSection16 } from '@/lib/hooks/use-section16';
import { setSection16Override, enterGrokScore } from '@/lib/api/section16';
import type {
  AppreciationStatus,
  GapDownStatus,
  PutProtectionStatus,
  Rule161Result,
  Rule161Status,
  Rule162Result,
  Rule163Result,
  Rule164Result,
  Section16OverallStatus,
} from '@/lib/schemas/section16';

// ---------------------------------------------------------------------------
// Named constants — no magic strings inline
// ---------------------------------------------------------------------------

/** Minimum override reason length (must match backend). */
const MIN_OVERRIDE_REASON_LEN = 50;

/** Overall status chip labels. */
const OVERALL_STATUS_LABEL: Record<Section16OverallStatus, string> = {
  ALL_CLEAR: 'ALL CLEAR',
  EXIT_ACTIVE: 'EXIT ACTIVE',
  PARTIAL_DATA: 'PARTIAL DATA',
  UNKNOWN: 'UNKNOWN',
};

/** Overall status chip CSS classes. */
const OVERALL_STATUS_CLASS: Record<Section16OverallStatus, string> = {
  ALL_CLEAR: 'is-s16-clear',
  EXIT_ACTIVE: 'is-s16-exit',
  PARTIAL_DATA: 'is-s16-partial',
  UNKNOWN: 'is-s16-unknown',
};

/** Rule 16.1 status labels. */
const RULE161_STATUS_LABEL: Record<Rule161Status, string> = {
  CLEAR: 'CLEAR',
  CYCLE_ONE: 'CYCLE ONE — WATCH',
  CYCLE_ONE_PAUSED: 'CYCLE ONE — PAUSED',
  CYCLE_TWO: 'CYCLE TWO — TRIM TRIGGERED',
  DEFERRED: 'DEFERRED',
  TRIM_TRIGGERED: 'TRIM EXECUTED',
  FULL_EXIT_TRIGGERED: 'FULL EXIT TRIGGERED',
  UNKNOWN: 'DATA UNAVAILABLE',
};

/** Rule 16.1 status chip CSS classes. */
const RULE161_STATUS_CLASS: Record<Rule161Status, string> = {
  CLEAR: 'is-s16-clear',
  CYCLE_ONE: 'is-s16-watch',
  CYCLE_ONE_PAUSED: 'is-s16-paused',
  CYCLE_TWO: 'is-s16-exit',
  DEFERRED: 'is-s16-deferred',
  TRIM_TRIGGERED: 'is-s16-exit',
  FULL_EXIT_TRIGGERED: 'is-s16-exit',
  UNKNOWN: 'is-s16-unknown',
};

/** Rule 16.2 status labels. */
const RULE162_STATUS_LABEL: Record<GapDownStatus, string> = {
  CLEAR: 'CLEAR',
  HOLDING: '48-HR HOLD ACTIVE',
  RESCORED: 'RESCORED',
  RESOLVED: 'RESOLVED',
  UNKNOWN: 'DATA UNAVAILABLE',
};

/** Rule 16.2 CSS classes. */
const RULE162_STATUS_CLASS: Record<GapDownStatus, string> = {
  CLEAR: 'is-s16-clear',
  HOLDING: 'is-s16-exit',
  RESCORED: 'is-s16-watch',
  RESOLVED: 'is-s16-clear',
  UNKNOWN: 'is-s16-unknown',
};

/** Rule 16.3 status labels. */
const RULE163_STATUS_LABEL: Record<AppreciationStatus, string> = {
  CLEAR: 'CLEAR',
  NO_NEW_CAPITAL: 'NO NEW CAPITAL',
  CONSIDER_TRIM: 'CONSIDER TRIM',
  UNKNOWN: 'DATA UNAVAILABLE',
};

/** Rule 16.3 CSS classes. */
const RULE163_STATUS_CLASS: Record<AppreciationStatus, string> = {
  CLEAR: 'is-s16-clear',
  NO_NEW_CAPITAL: 'is-s16-watch',
  CONSIDER_TRIM: 'is-s16-exit',
  UNKNOWN: 'is-s16-unknown',
};

/** Rule 16.4 status labels. */
const RULE164_STATUS_LABEL: Record<PutProtectionStatus, string> = {
  PUT_PROTECTION_RECOMMENDED: 'BUY PUTS',
  NOT_TRIGGERED: 'NOT TRIGGERED',
  UNKNOWN: 'DATA UNAVAILABLE',
};

/** Rule 16.4 CSS classes. */
const RULE164_STATUS_CLASS: Record<PutProtectionStatus, string> = {
  PUT_PROTECTION_RECOMMENDED: 'is-s16-exit',
  NOT_TRIGGERED: 'is-s16-clear',
  UNKNOWN: 'is-s16-unknown',
};

// ---------------------------------------------------------------------------
// Prop types
// ---------------------------------------------------------------------------

export type Section16CardProps = {
  /** Active ticker driven by the global ticker selector. */
  ticker: string;
};

// ---------------------------------------------------------------------------
// Pure formatting helpers
// ---------------------------------------------------------------------------

function fmtDate(isoStr: string | null | undefined): string {
  if (!isoStr) return '—';
  return isoStr.slice(0, 10);
}

function fmtScore(val: string | null | undefined): string {
  if (val === null || val === undefined) return '—';
  return parseFloat(val).toFixed(1);
}

function fmtPct(val: string | null | undefined): string {
  if (val === null || val === undefined) return '—';
  return `${parseFloat(val).toFixed(2)}%`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusChip({
  label,
  className,
}: {
  label: string;
  className: string;
}) {
  return (
    <span className={cn('atlas-s16-chip', className)}>{label}</span>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <h4 className="atlas-s16-section-header">{title}</h4>
  );
}

function DataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="atlas-s16-data-row">
      <span className="atlas-s16-data-label">{label}</span>
      <span className="atlas-s16-data-value">{value}</span>
    </div>
  );
}

function MissingSourceBadge({ source }: { source: string }) {
  return (
    <span className="atlas-s16-missing-badge">⚠ {source} unavailable</span>
  );
}

// ---------------------------------------------------------------------------
// Rule panels
// ---------------------------------------------------------------------------

function Rule161Panel({ result }: { result: Rule161Result }) {
  return (
    <div className="atlas-s16-rule-panel">
      <div className="atlas-s16-rule-header">
        <SectionHeader title="16.1 — Score-Based Exit" />
        <StatusChip
          label={RULE161_STATUS_LABEL[result.status]}
          className={RULE161_STATUS_CLASS[result.status]}
        />
      </div>

      <div className="atlas-s16-rule-body">
        <DataRow label="Cycle count" value={`${result.cycle_count} / 2`} />
        {result.triggering_score !== null && (
          <DataRow
            label="Triggering score"
            value={`${fmtScore(result.triggering_score)} (${fmtDate(result.triggering_date)})`}
          />
        )}
        {result.trim_triggered && result.trim_window_trading_days !== null && (
          <DataRow
            label="Trim window"
            value={`${result.trim_pct ?? '50'}% within ${result.trim_window_trading_days} trading days`}
          />
        )}
        {result.full_exit_triggered && result.exit_window_trading_days !== null && (
          <DataRow
            label="Exit window"
            value={`Full exit within ${result.exit_window_trading_days} trading days`}
          />
        )}
        {result.deferred_reason !== null && (
          <DataRow label="Deferred reason" value={result.deferred_reason} />
        )}
        {result.deferred_until !== null && (
          <DataRow label="Deferred until" value={fmtDate(result.deferred_until)} />
        )}

        {/* Reconciliation block */}
        {result.reconciliation_pending && (
          <div className="atlas-s16-recon-block">
            <span className="atlas-s16-recon-label">RECONCILIATION PENDING</span>
            <DataRow label="Claude score" value={fmtScore(result.claude_score)} />
            <DataRow label="Grok score" value={fmtScore(result.grok_score)} />
            {result.score_gap !== null && (
              <DataRow label="Gap" value={fmtScore(result.score_gap)} />
            )}
          </div>
        )}

        {result.missing_sources.map((src) => (
          <MissingSourceBadge key={src} source={src} />
        ))}
      </div>
    </div>
  );
}

function Rule162Panel({ result }: { result: Rule162Result }) {
  return (
    <div className="atlas-s16-rule-panel">
      <div className="atlas-s16-rule-header">
        <SectionHeader title="16.2 — Gap-Down Rule" />
        <StatusChip
          label={RULE162_STATUS_LABEL[result.status]}
          className={RULE162_STATUS_CLASS[result.status]}
        />
      </div>

      <div className="atlas-s16-rule-body">
        {result.gap_triggered ? (
          <>
            <DataRow
              label="Gap-down"
              value={result.gap_down_pct !== null ? fmtPct(result.gap_down_pct) : '—'}
            />
            <DataRow
              label="Prev close → Open"
              value={
                result.prev_close !== null && result.open_price !== null
                  ? `$${result.prev_close} → $${result.open_price}`
                  : '—'
              }
            />
            <DataRow label="Hold until" value={fmtDate(result.hold_until)} />
            <DataRow label="Rescore at" value={fmtDate(result.rescore_at)} />
          </>
        ) : (
          <span className="atlas-s16-no-signal">No gap-down event active.</span>
        )}

        {result.missing_sources.map((src) => (
          <MissingSourceBadge key={src} source={src} />
        ))}
      </div>
    </div>
  );
}

function Rule163Panel({ result }: { result: Rule163Result }) {
  return (
    <div className="atlas-s16-rule-panel">
      <div className="atlas-s16-rule-header">
        <SectionHeader title="16.3 — Appreciation Trim" />
        <StatusChip
          label={RULE163_STATUS_LABEL[result.status]}
          className={RULE163_STATUS_CLASS[result.status]}
        />
      </div>

      <div className="atlas-s16-rule-body">
        {result.position_pct_of_nav !== null && (
          <DataRow
            label="Position % of NAV"
            value={fmtPct(result.position_pct_of_nav)}
          />
        )}
        {result.consider_trim && result.trim_pct !== null && (
          <DataRow
            label="Trim recommendation"
            value={`Consider trimming ${result.trim_pct}% of position`}
          />
        )}
        {result.no_new_capital && !result.consider_trim && (
          <span className="atlas-s16-no-capital-note">
            No new capital to be deployed at this concentration level.
          </span>
        )}

        {result.missing_sources.map((src) => (
          <MissingSourceBadge key={src} source={src} />
        ))}
      </div>
    </div>
  );
}

function Rule164Panel({ result }: { result: Rule164Result }) {
  return (
    <div className="atlas-s16-rule-panel">
      <div className="atlas-s16-rule-header">
        <SectionHeader title="16.4 — Put Protection" />
        <StatusChip
          label={RULE164_STATUS_LABEL[result.status]}
          className={RULE164_STATUS_CLASS[result.status]}
        />
      </div>

      <div className="atlas-s16-rule-body">
        <div className="atlas-s16-conditions-list">
          {result.conditions.map((cond) => (
            <div
              key={cond.condition_number}
              className={cn(
                'atlas-s16-condition-row',
                cond.met === true
                  ? 'is-s16-cond-met'
                  : cond.met === false
                    ? 'is-s16-cond-unmet'
                    : 'is-s16-cond-unknown',
              )}
            >
              <span className="atlas-s16-cond-number">
                {cond.met === true ? '✓' : cond.met === false ? '✗' : '?'}
              </span>
              <span className="atlas-s16-cond-description">
                {cond.description}
              </span>
              {cond.value !== null && (
                <span className="atlas-s16-cond-value">
                  {cond.value}
                  {cond.threshold !== null && (
                    <span className="atlas-s16-cond-threshold">
                      {' '}(threshold: {cond.threshold})
                    </span>
                  )}
                </span>
              )}
            </div>
          ))}
        </div>

        {result.missing_sources.map((src) => (
          <MissingSourceBadge key={src} source={src} />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Override panel
// ---------------------------------------------------------------------------

function OverridePanel({
  ticker,
  isActive,
  reason,
  setBy,
  onOverrideSubmit,
}: {
  ticker: string;
  isActive: boolean;
  reason: string | null;
  setBy: string | null;
  onOverrideSubmit: () => void;
}) {
  const [overrideReason, setOverrideReason] = useState('');
  const [overrideBy, setOverrideBy] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (overrideReason.length < MIN_OVERRIDE_REASON_LEN) {
      setError(
        `Reason must be at least ${MIN_OVERRIDE_REASON_LEN} characters.`,
      );
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await setSection16Override(ticker, {
        reason: overrideReason,
        set_by: overrideBy || 'operator',
      });
      onOverrideSubmit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Override failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="atlas-s16-rule-panel">
      <SectionHeader title="Human Override" />

      {isActive ? (
        <div className="atlas-s16-override-active">
          <StatusChip label="OVERRIDE ACTIVE" className="is-s16-deferred" />
          {reason !== null && <DataRow label="Reason" value={reason} />}
          {setBy !== null && <DataRow label="Set by" value={setBy} />}
        </div>
      ) : (
        <div className="atlas-s16-override-form">
          <p className="atlas-s16-override-note">
            Override suppresses all automated exit signals. A written
            justification of at least {MIN_OVERRIDE_REASON_LEN} characters is
            required.
          </p>
          <textarea
            className="atlas-s16-textarea"
            placeholder="Override justification (min 50 characters)..."
            value={overrideReason}
            onChange={(e) => setOverrideReason(e.target.value)}
            rows={3}
          />
          <input
            className="atlas-s16-input"
            placeholder="Operator name / ID"
            value={overrideBy}
            onChange={(e) => setOverrideBy(e.target.value)}
          />
          {error !== null && (
            <span className="atlas-s16-error">{error}</span>
          )}
          <button
            className="atlas-s16-btn"
            disabled={submitting}
            onClick={handleSubmit}
            type="button"
          >
            {submitting ? 'Applying…' : 'Apply Override'}
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Grok reconciliation panel
// ---------------------------------------------------------------------------

function GrokPanel({
  ticker,
  result,
  onGrokSubmit,
}: {
  ticker: string;
  result: Rule161Result;
  onGrokSubmit: () => void;
}) {
  const [grokScore, setGrokScore] = useState('');
  const [enteredBy, setEnteredBy] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    const score = parseFloat(grokScore);
    if (isNaN(score) || score < 0 || score > 100) {
      setError('Score must be a number between 0 and 100.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await enterGrokScore(ticker, {
        score,
        score_date: new Date().toISOString().slice(0, 10),
        entered_by: enteredBy || 'operator',
        notes: notes || undefined,
      });
      onGrokSubmit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Grok score entry failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="atlas-s16-rule-panel">
      <SectionHeader title="Grok Reconciliation" />

      {result.reconciliation_pending ? (
        <div className="atlas-s16-recon-active">
          <StatusChip label="RECONCILIATION REQUIRED" className="is-s16-watch" />
          <DataRow label="Claude score" value={fmtScore(result.claude_score)} />
          <DataRow label="Current Grok" value={fmtScore(result.grok_score)} />
          <DataRow label="Gap" value={fmtScore(result.score_gap)} />
          <p className="atlas-s16-recon-note">
            Claude vs Grok gap exceeds threshold. Cycle clock is paused until
            reconciliation resolves. Enter the updated Grok score below.
          </p>
        </div>
      ) : (
        <p className="atlas-s16-no-signal">
          No reconciliation required.
          {result.grok_score !== null && (
            <> Last Grok score: {fmtScore(result.grok_score)}</>
          )}
        </p>
      )}

      <div className="atlas-s16-grok-form">
        <input
          className="atlas-s16-input"
          placeholder="Grok conviction score (0–100)"
          value={grokScore}
          onChange={(e) => setGrokScore(e.target.value)}
          type="number"
          min={0}
          max={100}
          step={0.1}
        />
        <input
          className="atlas-s16-input"
          placeholder="Entered by"
          value={enteredBy}
          onChange={(e) => setEnteredBy(e.target.value)}
        />
        <textarea
          className="atlas-s16-textarea"
          placeholder="Notes (optional)"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
        />
        {error !== null && <span className="atlas-s16-error">{error}</span>}
        <button
          className="atlas-s16-btn"
          disabled={submitting}
          onClick={handleSubmit}
          type="button"
        >
          {submitting ? 'Saving…' : 'Enter Grok Score'}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main card
// ---------------------------------------------------------------------------

export function Section16Card({ ticker }: Section16CardProps) {
  const { data, isLoading, isError, error } = useSection16(ticker);
  // Increment this to force a re-fetch after mutations.
  const [refetchKey, setRefetchKey] = useState(0);
  void refetchKey;

  function handleMutation() {
    setRefetchKey((k) => k + 1);
  }

  if (!ticker) {
    return (
      <div className="atlas-s16-card">
        <div className="atlas-s16-no-ticker">Select a ticker to evaluate exit rules.</div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="atlas-s16-card">
        <div className="atlas-s16-loading">Loading Section 16 exit rules for {ticker}…</div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="atlas-s16-card">
        <div className="atlas-s16-error-state">
          Failed to load Section 16 data.{' '}
          {error instanceof Error ? error.message : 'Unknown error.'}
        </div>
      </div>
    );
  }

  return (
    <div className="atlas-s16-card">
      {/* Header */}
      <div className="atlas-s16-card-header">
        <div className="atlas-s16-card-title">
          <span className="atlas-s16-section-label">SECTION 16</span>
          <span className="atlas-s16-card-name">Exit Rules</span>
          <span className="atlas-s16-ticker-badge">{ticker}</span>
        </div>
        <StatusChip
          label={OVERALL_STATUS_LABEL[data.overall_status]}
          className={OVERALL_STATUS_CLASS[data.overall_status]}
        />
      </div>

      {/* Override banner — shown above all rules when active */}
      {data.override_active && (
        <div className="atlas-s16-override-banner">
          <StatusChip label="HUMAN OVERRIDE ACTIVE — all exit signals suppressed" className="is-s16-deferred" />
          {data.override_reason !== null && (
            <p className="atlas-s16-override-banner-reason">{data.override_reason}</p>
          )}
        </div>
      )}

      {/* Rules grid */}
      <div className="atlas-s16-rules-grid">
        <Rule161Panel result={data.rule_161} />
        <Rule162Panel result={data.rule_162} />
        <Rule163Panel result={data.rule_163} />
        <Rule164Panel result={data.rule_164} />
      </div>

      {/* Grok reconciliation */}
      <GrokPanel
        ticker={ticker}
        result={data.rule_161}
        onGrokSubmit={handleMutation}
      />

      {/* Override panel */}
      <OverridePanel
        ticker={ticker}
        isActive={data.override_active}
        reason={data.override_reason}
        setBy={data.override_set_by}
        onOverrideSubmit={handleMutation}
      />

      {/* Footer */}
      <div className="atlas-s16-footer">
        <span className="atlas-s16-evaluated-at">
          Evaluated: {new Date(data.evaluated_at).toLocaleString()}
        </span>
      </div>
    </div>
  );
}
