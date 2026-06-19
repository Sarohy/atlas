'use client';

import { cn } from '@/lib/utils';
import { useState } from 'react';
import {
  useFramework17,
  useSetFramework17Flag,
  useFramework17History,
} from '@/lib/hooks/use-framework17';
import type { F17Severity, GeoFlagState } from '@/lib/schemas/framework17';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Minimum override reason length (must match backend). */
const MIN_OVERRIDE_REASON_LEN = 50;

/** Flag state chip labels. */
const FLAG_LABEL: Record<GeoFlagState, string> = {
  ACTIVE: 'ACTIVE RISK',
  DE_ESCALATING: 'DE-ESCALATING',
  NONE: 'NO RISK',
  NOT_SET: 'NOT SET',
};

/** Flag state chip CSS class suffixes. */
const FLAG_CHIP_CLASS: Record<GeoFlagState, string> = {
  ACTIVE: 'is-f17-active',
  DE_ESCALATING: 'is-f17-deescalating',
  NONE: 'is-f17-none',
  NOT_SET: 'is-f17-notset',
};

/** Severity badge classes. */
const SEVERITY_CLASS: Record<F17Severity, string> = {
  CRITICAL: 'is-f17-sev-critical',
  HIGH: 'is-f17-sev-high',
  ELEVATED: 'is-f17-sev-elevated',
  NONE: 'is-f17-sev-none',
  UNKNOWN: 'is-f17-sev-unknown',
};

/** This is a portfolio-level card — no ticker prop. */
export type Framework17CardProps = Record<string, never>;

// ---------------------------------------------------------------------------
// Pure formatting helpers
// ---------------------------------------------------------------------------

function formatBrent(val: number | null): string {
  if (val === null) return '—';
  return `$${val.toFixed(2)}/bbl`;
}

function formatDuration(days: number | null): string {
  if (days === null) return '—';
  return `${days}d`;
}

function formatDate(isoStr: string | null): string {
  if (!isoStr) return '—';
  return isoStr.slice(0, 10);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DataSourceBadge({ label, available }: { label: string; available: boolean }) {
  return (
    <span
      className={cn(
        'atlas-f17-source-badge',
        available ? 'is-f17-source-online' : 'is-f17-source-offline',
      )}
    >
      {label}: {available ? 'ONLINE' : 'OFFLINE'}
    </span>
  );
}

function StatRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: string;
}) {
  return (
    <div className="atlas-f17-stat-row">
      <span className="atlas-f17-stat-label">{label}</span>
      <span className={cn('atlas-f17-stat-value', highlight ?? '')}>{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Set flag form
// ---------------------------------------------------------------------------

function SetFlagForm({ onClose }: { onClose: () => void }) {
  const { mutateAsync, isPending, isError, error } = useSetFramework17Flag();

  const [flagState, setFlagState] = useState<GeoFlagState>('NONE');
  const [setBy, setSetBy] = useState('');
  const [conflictStartDate, setConflictStartDate] = useState('');
  const [notes, setNotes] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);

    if (overrideReason.trim().length < MIN_OVERRIDE_REASON_LEN) {
      setSubmitError(`Override reason must be at least ${MIN_OVERRIDE_REASON_LEN} characters.`);
      return;
    }

    try {
      await mutateAsync({
        flag_state: flagState as Exclude<GeoFlagState, 'NOT_SET'>,
        set_by: setBy.trim(),
        conflict_start_date: conflictStartDate || null,
        notes: notes.trim() || null,
        override_reason: overrideReason.trim(),
      });
      onClose();
    } catch {
      setSubmitError('Failed to set flag. Check backend connection.');
    }
  }

  return (
    <form className="atlas-f17-set-flag-form" onSubmit={handleSubmit}>
      <h4 className="atlas-f17-set-flag-title">Set Geopolitical Flag</h4>

      <div className="atlas-f17-form-field">
        <label className="atlas-f17-form-label">Flag State</label>
        <select
          className="atlas-f17-form-select"
          value={flagState}
          onChange={(e) => setFlagState(e.target.value as GeoFlagState)}
        >
          <option value="NONE">NONE — No active risk</option>
          <option value="DE_ESCALATING">DE_ESCALATING — Tensions cooling</option>
          <option value="ACTIVE">ACTIVE — Active geopolitical risk</option>
        </select>
      </div>

      <div className="atlas-f17-form-field">
        <label className="atlas-f17-form-label">Set By (operator ID)</label>
        <input
          className="atlas-f17-form-input"
          type="text"
          value={setBy}
          onChange={(e) => setSetBy(e.target.value)}
          required
          maxLength={100}
          placeholder="operator username or ID"
        />
      </div>

      {flagState === 'ACTIVE' && (
        <div className="atlas-f17-form-field">
          <label className="atlas-f17-form-label">Conflict Start Date</label>
          <input
            className="atlas-f17-form-input"
            type="date"
            value={conflictStartDate}
            onChange={(e) => setConflictStartDate(e.target.value)}
          />
        </div>
      )}

      <div className="atlas-f17-form-field">
        <label className="atlas-f17-form-label">Notes (optional)</label>
        <textarea
          className="atlas-f17-form-textarea"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          maxLength={2000}
          placeholder="Optional context notes"
        />
      </div>

      <div className="atlas-f17-form-field">
        <label className="atlas-f17-form-label">
          Override Reason (min {MIN_OVERRIDE_REASON_LEN} chars)
        </label>
        <textarea
          className="atlas-f17-form-textarea"
          value={overrideReason}
          onChange={(e) => setOverrideReason(e.target.value)}
          rows={3}
          placeholder={`Minimum ${MIN_OVERRIDE_REASON_LEN} characters required`}
          required
        />
        <span className="atlas-f17-char-count">
          {overrideReason.trim().length}/{MIN_OVERRIDE_REASON_LEN} chars
        </span>
      </div>

      {(submitError ?? (isError && error?.message)) && (
        <p className="atlas-f17-form-error">{submitError ?? error?.message}</p>
      )}

      <div className="atlas-f17-form-actions">
        <button type="button" className="atlas-f17-btn-cancel" onClick={onClose}>
          Cancel
        </button>
        <button type="submit" className="atlas-f17-btn-submit" disabled={isPending}>
          {isPending ? 'Saving…' : 'Set Flag'}
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main card
// ---------------------------------------------------------------------------

export function Framework17Card() {
  const { data, isLoading, isError } = useFramework17();
  const { data: history } = useFramework17History(14);
  const [showSetFlagForm, setShowSetFlagForm] = useState(false);

  if (isLoading) {
    return (
      <div className="atlas-f17-card atlas-f17-loading">Loading F17 Geopolitical Monitor…</div>
    );
  }

  if (isError || !data) {
    return (
      <div className="atlas-f17-card atlas-f17-error">F17 Geopolitical Monitor unavailable.</div>
    );
  }

  const chipClass = FLAG_CHIP_CLASS[data.flag_state];
  const sevClass = SEVERITY_CLASS[data.severity];

  return (
    <div className="atlas-f17-card" data-testid="framework17-card">
      {/* ── Section 1: Header ─────────────────────────────────────────── */}
      <div className="atlas-f17-header">
        <div className="atlas-f17-header-left">
          <span className="atlas-f17-framework-label">F17</span>
          <span className="atlas-f17-title">Geopolitical Monitor</span>
        </div>
        <div className="atlas-f17-header-right">
          <span className={cn('atlas-f17-flag-chip', chipClass)}>
            {FLAG_LABEL[data.flag_state]}
          </span>
          <span className={cn('atlas-f17-sev-badge', sevClass)}>{data.severity}</span>
        </div>
      </div>

      {/* ── Section 2: Briefing message ───────────────────────────────── */}
      <div
        className={cn(
          'atlas-f17-briefing',
          data.briefing_urgency === 'URGENT' && 'is-f17-briefing-urgent',
          data.briefing_urgency === 'WARNING' && 'is-f17-briefing-warning',
        )}
      >
        <p className="atlas-f17-briefing-text">{data.briefing_message}</p>
        {data.carried_forward && (
          <span className="atlas-f17-carried-forward-badge">
            ⚠ Carried forward from previous session
          </span>
        )}
      </div>

      {/* ── Section 3: Flag panel ─────────────────────────────────────── */}
      <div className="atlas-f17-flag-panel">
        <StatRow label="Flag State" value={FLAG_LABEL[data.flag_state]} />
        <StatRow label="Set By" value={data.set_by ?? '—'} />
        <StatRow
          label="Set At"
          value={data.set_at ? new Date(data.set_at).toLocaleString() : '—'}
        />
        {data.notes && <StatRow label="Notes" value={data.notes} />}
      </div>

      {/* ── Section 4: Conflict details ───────────────────────────────── */}
      <div className="atlas-f17-conflict-panel">
        <StatRow label="Conflict Start" value={formatDate(data.conflict_start_date)} />
        <StatRow
          label="Duration"
          value={formatDuration(data.conflict_duration_days)}
          highlight={
            data.conflict_duration_days !== null && data.conflict_duration_days > 30
              ? 'is-f17-value-warn'
              : undefined
          }
        />
        <StatRow
          label="Brent Crude"
          value={formatBrent(data.brent_price)}
          highlight={
            data.brent_price !== null && data.brent_price > 110
              ? 'is-f17-value-critical'
              : data.brent_price !== null && data.brent_price > 95
                ? 'is-f17-value-warn'
                : undefined
          }
        />
      </div>

      {/* ── Section 5: CLEAR regime impact ───────────────────────────── */}
      <div className="atlas-f17-regime-panel">
        <StatRow
          label="Regime"
          value={data.regime ?? (data.regime_available ? '—' : 'UNAVAILABLE')}
        />
        <StatRow
          label="CLEAR Possible"
          value={data.clear_regime_possible ? 'YES' : 'NO'}
          highlight={data.clear_regime_possible ? 'is-f17-value-ok' : 'is-f17-value-warn'}
        />
        {data.clear_regime_blocked && (
          <p className="atlas-f17-regime-blocked-note">
            ACTIVE geo flag is blocking CLEAR regime (F2 integration active).
          </p>
        )}
      </div>

      {/* ── Section 6: Operator action ───────────────────────────────── */}
      <div className="atlas-f17-operator-section">
        {!showSetFlagForm ? (
          <button className="atlas-f17-set-flag-btn" onClick={() => setShowSetFlagForm(true)}>
            Update Geopolitical Flag
          </button>
        ) : (
          <SetFlagForm onClose={() => setShowSetFlagForm(false)} />
        )}
      </div>

      {/* ── Section 7: Flag history ───────────────────────────────────── */}
      {history && history.length > 0 && (
        <div className="atlas-f17-history-section">
          <h4 className="atlas-f17-section-title">Flag History (last 14 days)</h4>
          <div className="atlas-f17-history-list">
            {history.slice(0, 7).map((entry) => (
              <div key={entry.id} className="atlas-f17-history-row">
                <span className={cn('atlas-f17-history-state', FLAG_CHIP_CLASS[entry.flag_state])}>
                  {FLAG_LABEL[entry.flag_state]}
                </span>
                <span className="atlas-f17-history-date">{entry.session_date}</span>
                <span className="atlas-f17-history-by">{entry.set_by}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Section 8: Data source badges ────────────────────────────── */}
      <div className="atlas-f17-sources">
        <DataSourceBadge label="F17 DB" available={data.flag_state !== 'NOT_SET'} />
        <DataSourceBadge label="Framework 2" available={data.regime_available} />
        <DataSourceBadge label="Polygon Brent" available={data.brent_price !== null} />
      </div>

      {/* ── Section 9: Cache info ─────────────────────────────────────── */}
      {data.data_as_of && (
        <div className="atlas-f17-footer">
          <span className="atlas-f17-data-as-of">
            As of {new Date(data.data_as_of).toLocaleTimeString()}
            {data.cache_hit && ' · cached'}
          </span>
        </div>
      )}
    </div>
  );
}
