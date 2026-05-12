'use client';

import { cn } from '@/lib/utils';
import { useState } from 'react';

import {
  useFramework27,
  usePostFramework27ManualFlag,
} from '@/lib/hooks/use-framework27';
import type {
  ContagionRuleResult,
  Framework27Result,
} from '@/lib/schemas/framework27';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Minimum override reason length — must match backend validation. */
const MIN_OVERRIDE_REASON_LEN = 50;

/** Allowed trigger types for the manual flag form. */
const TRIGGER_TYPES = [
  'ASIA_FREIGHT_DISRUPTION_PCT',
  'METALS_DISRUPTION',
  'INDIUM_SUPPLY_DISRUPTION',
] as const;

type TriggerType = (typeof TRIGGER_TYPES)[number];

/** Human-readable labels for each trigger type. */
const TRIGGER_LABELS: Record<TriggerType, string> = {
  ASIA_FREIGHT_DISRUPTION_PCT: 'Asia Freight Disruption',
  METALS_DISRUPTION: 'Metals Supply Disruption',
  INDIUM_SUPPLY_DISRUPTION: 'Indium Supply Disruption',
};

// ---------------------------------------------------------------------------
// Pure formatting helpers
// ---------------------------------------------------------------------------

function formatBrent(price: number | null): string {
  if (price === null) return '—';
  return `$${price.toFixed(2)}/bbl`;
}

function formatDays(days: number | null): string {
  if (days === null) return '—';
  return `${days}d`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

type F27StatusChipProps = { triggered: number; total: number };

function F27StatusChip({ triggered, total }: F27StatusChipProps) {
  const isActive = triggered > 0;
  return (
    <div className="atlas-f27-header-right">
      <span
        data-testid="f27-status-chip"
        className={cn(
          'atlas-f27-status-chip',
          isActive ? 'is-f27-triggered' : 'is-f27-clear',
        )}
      >
        {isActive ? 'TRIGGERED' : 'CLEAR'}
      </span>
      <span data-testid="f27-rules-count" className="atlas-f27-rules-count">
        {triggered}&nbsp;/&nbsp;{total}
      </span>
    </div>
  );
}

function F27RuleRow({ rule }: { rule: ContagionRuleResult }) {
  return (
    <div
      data-testid={`f27-rule-row-${rule.rule_id}`}
      className={cn(
        'atlas-f27-rule-row',
        rule.triggered ? 'is-f27-rule-triggered' : '',
      )}
    >
      <span className="atlas-f27-rule-ticker">{rule.ticker}</span>
      <span className="atlas-f27-rule-risk">{rule.primary_risk}</span>
      <span className="atlas-f27-rule-type">{rule.contagion_trigger_type}</span>
      <span
        className={cn(
          'atlas-f27-rule-status',
          rule.triggered ? 'is-f27-triggered' : 'is-f27-clear',
        )}
      >
        {rule.triggered ? '⚡ TRIGGERED' : 'CLEAR'}
      </span>
    </div>
  );
}

function F27F17Badge({ active }: { active: boolean | null }) {
  return (
    <div className="atlas-f27-context-row">
      <span
        data-testid="f27-f17-badge"
        className={cn(
          'atlas-f27-f17-badge',
          active === true ? 'is-f27-f17-active' : '',
        )}
      >
        F17 GEO: {active === true ? 'ACTIVE' : active === false ? 'CLEAR' : 'NOT SET'}
      </span>
    </div>
  );
}

function F27ContextRow({ data }: { data: Framework27Result }) {
  return (
    <div className="atlas-f27-context-grid">
      <F27F17Badge active={data.f17_active} />
      <div className="atlas-f27-stat-row">
        <span className="atlas-f27-stat-label">Brent</span>
        <span
          data-testid="f27-brent-price"
          className="atlas-f27-stat-value"
        >
          {formatBrent(data.brent_price)}
        </span>
      </div>
      <div className="atlas-f27-stat-row">
        <span className="atlas-f27-stat-label">Conflict duration</span>
        <span className="atlas-f27-stat-value">
          {formatDays(data.conflict_duration_days)}
        </span>
      </div>
    </div>
  );
}

function F27OperatorFlags({ data }: { data: Framework27Result }) {
  return (
    <div data-testid="f27-operator-flags" className="atlas-f27-operator-flags">
      <span className="atlas-f27-flags-label">Operator flags</span>
      <div className="atlas-f27-flags-row">
        <span
          data-testid="f27-flag-asia"
          className={cn(
            'atlas-f27-flag-badge',
            data.asia_freight_flagged ? 'is-f27-flag-active' : '',
          )}
        >
          ASIA FREIGHT
        </span>
        <span
          data-testid="f27-flag-metals"
          className={cn(
            'atlas-f27-flag-badge',
            data.metals_disruption_flagged ? 'is-f27-flag-active' : '',
          )}
        >
          METALS
        </span>
        <span
          data-testid="f27-flag-indium"
          className={cn(
            'atlas-f27-flag-badge',
            data.indium_disruption_flagged ? 'is-f27-flag-active' : '',
          )}
        >
          INDIUM
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Manual flag form
// ---------------------------------------------------------------------------

function F27FormFields({
  triggerType,
  flaggedBy,
  notes,
  overrideReason,
  onTriggerTypeChange,
  onFlaggedByChange,
  onNotesChange,
  onOverrideReasonChange,
}: {
  triggerType: TriggerType;
  flaggedBy: string;
  notes: string;
  overrideReason: string;
  onTriggerTypeChange: (v: TriggerType) => void;
  onFlaggedByChange: (v: string) => void;
  onNotesChange: (v: string) => void;
  onOverrideReasonChange: (v: string) => void;
}) {
  return (
    <>
      <div className="atlas-f27-form-field">
        <label className="atlas-f27-form-label">Disruption Type</label>
        <select
          className="atlas-f27-form-select"
          value={triggerType}
          onChange={(e) => onTriggerTypeChange(e.target.value as TriggerType)}
        >
          {TRIGGER_TYPES.map((t) => (
            <option key={t} value={t}>
              {TRIGGER_LABELS[t]}
            </option>
          ))}
        </select>
      </div>

      <div className="atlas-f27-form-field">
        <label className="atlas-f27-form-label">Flagged By (operator ID)</label>
        <input
          className="atlas-f27-form-input"
          type="text"
          value={flaggedBy}
          onChange={(e) => onFlaggedByChange(e.target.value)}
          required
          maxLength={100}
          placeholder="operator username or ID"
        />
      </div>

      <div className="atlas-f27-form-field">
        <label className="atlas-f27-form-label">Notes (optional)</label>
        <textarea
          className="atlas-f27-form-textarea"
          value={notes}
          onChange={(e) => onNotesChange(e.target.value)}
          rows={2}
          maxLength={2000}
          placeholder="Optional context notes"
        />
      </div>

      <div className="atlas-f27-form-field">
        <label className="atlas-f27-form-label">
          Override Reason (min {MIN_OVERRIDE_REASON_LEN} chars)
        </label>
        <textarea
          className="atlas-f27-form-textarea"
          value={overrideReason}
          onChange={(e) => onOverrideReasonChange(e.target.value)}
          rows={3}
          placeholder={`Minimum ${MIN_OVERRIDE_REASON_LEN} characters required`}
          required
        />
        <span className="atlas-f27-char-count">
          {overrideReason.trim().length}/{MIN_OVERRIDE_REASON_LEN} chars
        </span>
      </div>
    </>
  );
}

function F27ManualFlagForm({ onClose }: { onClose: () => void }) {
  const { mutateAsync, isPending, isError, error } =
    usePostFramework27ManualFlag();

  const [triggerType, setTriggerType] = useState<TriggerType>(
    'ASIA_FREIGHT_DISRUPTION_PCT',
  );
  const [flaggedBy, setFlaggedBy] = useState('');
  const [notes, setNotes] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);

    if (overrideReason.trim().length < MIN_OVERRIDE_REASON_LEN) {
      setSubmitError(
        `Override reason must be at least ${MIN_OVERRIDE_REASON_LEN} characters.`,
      );
      return;
    }

    try {
      await mutateAsync({
        trigger_type: triggerType,
        flagged_by: flaggedBy.trim(),
        notes: notes.trim() || null,
        override_reason: overrideReason.trim(),
      });
      onClose();
    } catch {
      setSubmitError('Failed to submit flag. Check backend connection.');
    }
  }

  const displayError = submitError ?? (isError ? (error?.message ?? null) : null);

  return (
    <form
      data-testid="f27-flag-form"
      className="atlas-f27-flag-form"
      onSubmit={handleSubmit}
    >
      <h4 className="atlas-f27-flag-form-title">Manual Disruption Flag</h4>

      <F27FormFields
        triggerType={triggerType}
        flaggedBy={flaggedBy}
        notes={notes}
        overrideReason={overrideReason}
        onTriggerTypeChange={setTriggerType}
        onFlaggedByChange={setFlaggedBy}
        onNotesChange={setNotes}
        onOverrideReasonChange={setOverrideReason}
      />

      {displayError !== null && (
        <p className="atlas-f27-form-error">{displayError}</p>
      )}

      <div className="atlas-f27-form-actions">
        <button
          type="submit"
          disabled={isPending}
          className="atlas-f27-submit-btn"
        >
          {isPending ? 'Submitting…' : 'Submit Flag'}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="atlas-f27-cancel-btn"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main card
// ---------------------------------------------------------------------------

/** Framework 27 is portfolio-level — no ticker prop. */
export type Framework27CardProps = Record<string, never>;

function F27CardHeader() {
  return (
    <div className="atlas-f27-header">
      <div className="atlas-f27-header-left">
        <span className="atlas-f27-framework-label">FRAMEWORK 27</span>
        <span className="atlas-f27-title">Supply Chain Contagion Map</span>
      </div>
    </div>
  );
}

export function Framework27Card(_props: Framework27CardProps) {
  const { data, isLoading, isError, error } = useFramework27();
  const [formOpen, setFormOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="atlas-f27-card">
        <F27CardHeader />
        <div data-testid="f27-loading" className="atlas-f27-loading">
          Loading Supply Chain Contagion Map…
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="atlas-f27-card">
        <F27CardHeader />
        <div data-testid="f27-error" className="atlas-f27-error">
          {error instanceof Error
            ? error.message
            : 'Failed to load Framework 27 data.'}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'atlas-f27-card',
        data.rules_triggered > 0 ? 'is-f27-card-triggered' : '',
      )}
    >
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="atlas-f27-header">
        <div className="atlas-f27-header-left">
          <span className="atlas-f27-framework-label">FRAMEWORK 27</span>
          <span className="atlas-f27-title">Supply Chain Contagion Map</span>
        </div>
        <div className="atlas-f27-header-badges">
          <F27StatusChip
            triggered={data.rules_triggered}
            total={data.rules_evaluated}
          />
          {data.cache_hit && (
            <span
              data-testid="f27-cache-badge"
              className="atlas-f27-cache-badge"
              title={`Cached. As of: ${data.data_as_of ?? '—'}`}
            >
              CACHED
            </span>
          )}
        </div>
      </div>

      {/* ── F17 context ───────────────────────────────────────────────────── */}
      <F27ContextRow data={data} />

      {/* ── Operator flags ────────────────────────────────────────────────── */}
      <F27OperatorFlags data={data} />

      {/* ── Rules table ───────────────────────────────────────────────────── */}
      <div data-testid="f27-rules-table" className="atlas-f27-rules-table">
        <div className="atlas-f27-rules-header">
          <span>Ticker</span>
          <span>Primary Risk</span>
          <span>Trigger Type</span>
          <span>Status</span>
        </div>
        {data.all_rules.map((rule) => (
          <F27RuleRow key={rule.rule_id} rule={rule} />
        ))}
        {data.all_rules.length === 0 && (
          <div className="atlas-f27-rules-empty">No contagion rules configured.</div>
        )}
      </div>

      {/* ── Manual flag ───────────────────────────────────────────────────── */}
      {formOpen ? (
        <F27ManualFlagForm onClose={() => setFormOpen(false)} />
      ) : (
        <button
          data-testid="f27-open-flag-form"
          type="button"
          className="atlas-f27-open-flag-btn"
          onClick={() => setFormOpen(true)}
        >
          + Add Manual Flag
        </button>
      )}
    </div>
  );
}
