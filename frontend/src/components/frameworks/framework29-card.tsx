'use client';

import { cn } from '@/lib/utils';
import { useF29Evaluation } from '@/lib/hooks/use-f29-evaluation';
import type {
  F29CatalystValidatedEvaluation,
  F29DiscretionaryEvaluation,
  F29EntryType,
  F29GateStatus,
  F29RegimePrecondition,
  F29WashoutEvaluation,
} from '@/lib/schemas/framework29';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** CSS class per gate status. UNAVAILABLE = amber, never red. */
const GATE_STATUS_CLASS: Record<F29GateStatus, string> = {
  PASS: 'is-f29-gate-pass',
  BLOCKED: 'is-f29-gate-blocked',
  UNAVAILABLE: 'is-f29-gate-unavailable',
};

/** Human-readable gate status label. */
const GATE_STATUS_LABEL: Record<F29GateStatus, string> = {
  PASS: 'LEAPS PERMITTED',
  BLOCKED: 'LEAPS BLOCKED',
  UNAVAILABLE: 'DATA UNAVAILABLE',
};

/** Human-readable entry type label. */
const ENTRY_TYPE_LABEL: Record<F29EntryType, string> = {
  WASHOUT: 'WASHOUT',
  CATALYST_VALIDATED: 'CATALYST VALIDATED',
  DISCRETIONARY: 'DISCRETIONARY',
  BLOCKED_BY_REGIME: 'BLOCKED BY REGIME',
  UNAVAILABLE: 'UNAVAILABLE',
};

/** ConditionMet display helpers. */
function metLabel(met: boolean | 'UNAVAILABLE'): string {
  if (met === 'UNAVAILABLE') return 'UNAVAILABLE';
  return met ? 'MET' : 'NOT MET';
}

function metClass(met: boolean | 'UNAVAILABLE'): string {
  if (met === 'UNAVAILABLE') return 'is-f29-cond-unavailable';
  return met ? 'is-f29-cond-met' : 'is-f29-cond-not-met';
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RegimePreconditionCard({ regime }: { regime: F29RegimePrecondition }) {
  const chipClass = regime.passed
    ? 'is-f29-cond-met'
    : regime.regime_undefined_flag
      ? 'is-f29-gate-unavailable'
      : 'is-f29-gate-blocked';

  return (
    <div className="atlas-f29-regime-card" data-testid="f29-regime-precondition">
      <div className="atlas-f29-regime-header">
        <span className="atlas-f29-regime-label">Regime</span>
        <span className={cn('atlas-f29-regime-chip', chipClass)} data-testid="f29-regime-chip">
          {regime.regime}
        </span>
        {regime.regime_undefined_flag && (
          <span
            className="atlas-f29-regime-undefined-badge"
            data-testid="f29-regime-undefined-badge"
          >
            REGIME_UNDEFINED
          </span>
        )}
      </div>
      {regime.reason && (
        <p className="atlas-f29-regime-reason" data-testid="f29-regime-reason">
          {regime.reason}
        </p>
      )}
    </div>
  );
}

function WashoutDetail({
  evaluation,
  isActive,
}: {
  evaluation: F29WashoutEvaluation;
  isActive: boolean;
}) {
  return (
    <div
      className={cn('atlas-f29-path-card', isActive && 'is-f29-path-active')}
      data-testid="f29-washout-detail"
    >
      <div className="atlas-f29-path-card-header">
        <span className="atlas-f29-path-label">Path A — WASHOUT</span>
        <span
          className={cn('atlas-f29-path-matched-chip', evaluation.matched ? 'is-f29-cond-met' : '')}
          data-testid="f29-washout-matched"
        >
          {evaluation.matched ? 'MATCHED' : 'NOT MATCHED'}
        </span>
      </div>
      <ul className="atlas-f29-conditions-list">
        {evaluation.conditions.map((cond) => (
          <li key={cond.id} className="atlas-f29-condition-row">
            <span className={cn('atlas-f29-cond-chip', metClass(cond.met))} data-testid={`f29-washout-cond-${cond.id}`}>
              {metLabel(cond.met)}
            </span>
            <span className="atlas-f29-cond-reason">{cond.reason}</span>
            {cond.value !== null && (
              <span className="atlas-f29-cond-value">({cond.value})</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CatalystDetail({
  evaluation,
  isActive,
}: {
  evaluation: F29CatalystValidatedEvaluation;
  isActive: boolean;
}) {
  return (
    <div
      className={cn('atlas-f29-path-card', isActive && 'is-f29-path-active')}
      data-testid="f29-catalyst-detail"
    >
      <div className="atlas-f29-path-card-header">
        <span className="atlas-f29-path-label">Path B — CATALYST VALIDATED</span>
        <span
          className={cn('atlas-f29-path-matched-chip', evaluation.matched ? 'is-f29-cond-met' : '')}
          data-testid="f29-catalyst-matched"
        >
          {evaluation.matched ? 'MATCHED' : 'NOT MATCHED'}
        </span>
      </div>
      <div className="atlas-f29-catalyst-preconditions">
        <span className={cn('atlas-f29-cond-chip', metClass(evaluation.position_held))} data-testid="f29-catalyst-position-held">
          Position held: {metLabel(evaluation.position_held)}
        </span>
        <span className={cn('atlas-f29-cond-chip', metClass(evaluation.score_tier_pass))} data-testid="f29-catalyst-score-pass">
          Score ≥ T2: {metLabel(evaluation.score_tier_pass)}
        </span>
      </div>
      <p className="atlas-f29-sub-conditions-count" data-testid="f29-catalyst-sub-count">
        Sub-conditions met: {evaluation.sub_conditions_met_count} / {evaluation.sub_conditions.length}
      </p>
      <ul className="atlas-f29-conditions-list">
        {evaluation.sub_conditions.map((sc) => (
          <li key={sc.id} className="atlas-f29-condition-row">
            <span className={cn('atlas-f29-cond-chip', metClass(sc.met))} data-testid={`f29-catalyst-sub-${sc.id}`}>
              {metLabel(sc.met)}
            </span>
            <span className="atlas-f29-cond-reason">{sc.reason}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DiscretionaryDetail({ evaluation }: { evaluation: F29DiscretionaryEvaluation }) {
  return (
    <div
      className="atlas-f29-path-card is-f29-path-active"
      data-testid="f29-discretionary-detail"
    >
      <div className="atlas-f29-path-card-header">
        <span className="atlas-f29-path-label">Path C — DISCRETIONARY</span>
        <span className="atlas-f29-disc-threshold" data-testid="f29-disc-threshold">
          {evaluation.signals_met} / {evaluation.signals.length} signals
          {evaluation.threshold_inferred && (
            <span
              className="atlas-f29-threshold-inferred-badge"
              data-testid="f29-threshold-inferred-badge"
            >
              THRESHOLD_INFERRED
            </span>
          )}
        </span>
      </div>
      <ul className="atlas-f29-conditions-list">
        {evaluation.signals.map((sig) => (
          <li key={sig.id} className="atlas-f29-condition-row">
            <span className={cn('atlas-f29-cond-chip', metClass(sig.met))} data-testid={`f29-disc-signal-${sig.id}`}>
              {metLabel(sig.met)}
            </span>
            <span className="atlas-f29-cond-reason">{sig.label}</span>
            {sig.value !== null && (
              <span className="atlas-f29-cond-value">({sig.value})</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function DataGapsSection({ gaps }: { gaps: string[] }) {
  if (gaps.length === 0) return null;
  return (
    <div className="atlas-f29-data-gaps" data-testid="f29-data-gaps">
      <h3 className="atlas-f29-data-gaps-title">Data Gaps</h3>
      <ul className="atlas-f29-data-gaps-list">
        {gaps.map((gap, idx) => (
          <li key={idx} className="atlas-f29-data-gap-item">
            {gap}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Framework29CardProps {
  ticker: string;
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 29 — Three-Path Entry Classifier card.
 *
 * Displays the per-ticker LEAPS entry classification:
 *   1. Regime precondition (CRISIS_HALT = hard stop)
 *   2. Gate status header chip (PASS / BLOCKED / UNAVAILABLE)
 *   3. Path breakdown (all three paths shown; matched one highlighted)
 *   4. Data gaps (first-class section — amber, never red)
 *
 * Requires a non-empty ticker prop; renders a placeholder when ticker is empty.
 */
export function Framework29Card({ ticker }: Framework29CardProps) {
  const { data, isLoading, isError, error } = useF29Evaluation(ticker);
  const errorMsg =
    error instanceof Error ? error.message : 'Failed to load F29 classifier data.';

  const noTicker = !ticker || ticker.trim().length === 0;

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-f29-panel"
      data-testid="framework29-card"
    >
      {/* ── Header ── */}
      <header className="atlas-f29-header">
        <div className="atlas-f29-header-left">
          <h2 className="atlas-frameworks-panel-title">Framework 29</h2>
          <span className="atlas-fws-subtitle">LEAPS Entry Classifier</span>
          {ticker && (
            <span className="atlas-f29-ticker-badge" data-testid="f29-ticker-badge">
              {ticker}
            </span>
          )}
        </div>
        {data !== undefined && (
          <span
            className={cn('atlas-f29-gate-chip', GATE_STATUS_CLASS[data.gate_status])}
            data-testid="f29-gate-chip"
          >
            {GATE_STATUS_LABEL[data.gate_status]}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {/* ── State guards ── */}
        {noTicker && (
          <p className="atlas-fws-state-msg" data-testid="f29-no-ticker">
            Select a ticker to evaluate LEAPS eligibility.
          </p>
        )}

        {!noTicker && isLoading && (
          <p className="atlas-fws-state-msg" data-testid="f29-loading">
            Evaluating {ticker}…
          </p>
        )}

        {!noTicker && isError && (
          <p
            className="atlas-fws-state-msg atlas-fws-state-msg--error"
            data-testid="f29-error"
          >
            {errorMsg}
          </p>
        )}

        {!noTicker && !isLoading && !isError && data !== undefined && (
          <>
            {/* ── Entry type summary ── */}
            <div className="atlas-f29-entry-type-row" data-testid="f29-entry-type-row">
              <span className="atlas-f29-entry-type-label">Entry type:</span>
              <span
                className={cn('atlas-f29-entry-type-chip', GATE_STATUS_CLASS[data.gate_status])}
                data-testid="f29-entry-type"
              >
                {ENTRY_TYPE_LABEL[data.entry_type]}
              </span>
            </div>

            {/* ── Step 0: Regime precondition ── */}
            <RegimePreconditionCard regime={data.regime_precondition} />

            {/* ── Path evaluations (all shown; active one highlighted) ── */}
            {/* If CRISIS_HALT or REGIME_UNDEFINED, path cards are grayed out */}
            <div
              className={cn(
                'atlas-f29-paths',
                !data.regime_precondition.passed && 'is-f29-paths-greyed',
              )}
              data-testid="f29-paths"
            >
              <WashoutDetail
                evaluation={data.washout_evaluation}
                isActive={data.entry_type === 'WASHOUT'}
              />
              <CatalystDetail
                evaluation={data.catalyst_validated_evaluation}
                isActive={data.entry_type === 'CATALYST_VALIDATED'}
              />
              {/* DISCRETIONARY path only rendered when it is the active path */}
              {data.entry_type === 'DISCRETIONARY' &&
                data.discretionary_evaluation !== null && (
                  <DiscretionaryDetail evaluation={data.discretionary_evaluation} />
                )}
            </div>

            {/* ── Data gaps (first-class, amber) ── */}
            <DataGapsSection gaps={data.all_data_gaps} />
          </>
        )}
      </div>
    </section>
  );
}


