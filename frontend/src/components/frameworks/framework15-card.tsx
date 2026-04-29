'use client';

import { cn } from '@/lib/utils';
import { useFramework15 } from '@/lib/hooks/use-framework15';
import { useAddOverride, useReviewPausedOrder } from '@/lib/hooks/use-framework15';
import { useState } from 'react';
import type { F15Status, Framework15Result, PausedOrder } from '@/lib/schemas/framework15';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Minimum override reason length (must match backend). */
const MIN_OVERRIDE_REASON_LEN = 50;

/** F15 status chip labels. */
const STATUS_LABEL: Record<F15Status, string> = {
  ACTIVE: 'HALT ACTIVE',
  CLEAR: 'CLEAR',
  UNKNOWN: 'UNKNOWN',
  OUTSIDE_HOURS: 'OUTSIDE HOURS',
};

/** F15 status chip CSS class suffixes. */
const STATUS_CHIP_CLASS: Record<F15Status, string> = {
  ACTIVE: 'is-f15-active',
  CLEAR: 'is-f15-clear',
  UNKNOWN: 'is-f15-unknown',
  OUTSIDE_HOURS: 'is-f15-outside-hours',
};

/** F15 status panel CSS class suffixes. */
const STATUS_PANEL_CLASS: Record<F15Status, string> = {
  ACTIVE: 'is-f15-panel-active',
  CLEAR: 'is-f15-panel-clear',
  UNKNOWN: 'is-f15-panel-unknown',
  OUTSIDE_HOURS: 'is-f15-panel-outside-hours',
};

/** Review decision labels. */
const REVIEW_LABELS: Record<string, string> = {
  KEEP: 'Keep',
  MODIFY: 'Modify',
  CANCEL: 'Cancel',
};

/** This is a portfolio-level card — no ticker prop. */
export type Framework15CardProps = Record<string, never>;

// ---------------------------------------------------------------------------
// Pure formatting helpers
// ---------------------------------------------------------------------------

function formatVix(val: number | null): string {
  if (val === null) return '—';
  return val.toFixed(2);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: string;
}) {
  return (
    <div className="atlas-f15-stat-card">
      <span className="atlas-f15-stat-label">{label}</span>
      <span className={cn('atlas-f15-stat-value', highlight ?? '')}>{value}</span>
    </div>
  );
}

function DataSourceBadge({
  label,
  available,
}: {
  label: string;
  available: boolean;
}) {
  return (
    <span
      className={cn(
        'atlas-f15-source-badge',
        available ? 'is-f15-source-online' : 'is-f15-source-offline',
      )}
      data-testid={`f15-source-${label.toLowerCase().replace(/\s+/g, '-')}`}
    >
      {label}: {available ? 'ONLINE' : 'OFFLINE'}
    </span>
  );
}

function ActionChip({
  label,
  blocked,
}: {
  label: string;
  blocked: boolean;
}) {
  return (
    <span
      className={cn(
        'atlas-f15-action-chip',
        blocked ? 'is-f15-action-blocked' : 'is-f15-action-permitted',
      )}
    >
      {blocked ? '✗' : '✓'} {label}
    </span>
  );
}

function PausedOrderRow({
  order,
  onReview,
}: {
  order: PausedOrder;
  onReview: (orderId: number, decision: string) => void;
}) {
  const isPending = order.review_status === 'PENDING_REVIEW';
  return (
    <tr
      className={cn(
        'atlas-f15-order-row',
        isPending ? 'is-f15-order-pending' : 'is-f15-order-reviewed',
      )}
      data-testid={`f15-order-row-${order.order_id}`}
    >
      <td className="atlas-f15-order-cell">{order.ticker}</td>
      <td className="atlas-f15-order-cell">{order.order_type}</td>
      <td className="atlas-f15-order-cell">{order.paused_at}</td>
      <td className="atlas-f15-order-cell">{order.review_status}</td>
      <td className="atlas-f15-order-cell">
        {isPending ? (
          <span className="atlas-f15-order-actions">
            {Object.entries(REVIEW_LABELS).map(([decision, label]) => (
              <button
                key={decision}
                className={`atlas-f15-review-btn is-f15-review-${decision.toLowerCase()}`}
                onClick={() => onReview(order.order_id, decision)}
                type="button"
              >
                {label}
              </button>
            ))}
          </span>
        ) : (
          <span className="atlas-f15-order-reviewed-label">Reviewed</span>
        )}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Override form sub-component
// ---------------------------------------------------------------------------

function OverrideForm({
  onSubmit,
  isPending,
}: {
  onSubmit: (reason: string, restoreTypes: string[]) => void;
  isPending: boolean;
}) {
  const [reason, setReason] = useState('');
  const [restoreInput, setRestoreInput] = useState('');

  const isValid = reason.trim().length >= MIN_OVERRIDE_REASON_LEN;
  const charCount = reason.trim().length;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid) return;
    const restoreTypes = restoreInput
      .split(',')
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    onSubmit(reason.trim(), restoreTypes);
  }

  return (
    <form onSubmit={handleSubmit} className="atlas-f15-override-form" data-testid="f15-override-form">
      <label className="atlas-f15-override-label" htmlFor="f15-override-reason">
        Override Justification
        <span className={cn('atlas-f15-char-count', isValid ? 'is-f15-char-valid' : 'is-f15-char-invalid')}>
          {' '}({charCount}/{MIN_OVERRIDE_REASON_LEN} min)
        </span>
      </label>
      <textarea
        id="f15-override-reason"
        className={cn('atlas-f15-override-textarea', !isValid && reason.length > 0 ? 'is-f15-textarea-invalid' : '')}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Provide detailed justification for overriding the F15 VIX session halt..."
        rows={4}
        required
        data-testid="f15-override-reason"
      />
      <label className="atlas-f15-override-label" htmlFor="f15-restore-types">
        Restore Order Types (comma-separated, e.g. MARKET,LIMIT)
      </label>
      <input
        id="f15-restore-types"
        className="atlas-f15-restore-input"
        value={restoreInput}
        onChange={(e) => setRestoreInput(e.target.value)}
        placeholder="MARKET, LIMIT, GTC"
        type="text"
        data-testid="f15-restore-types"
      />
      <button
        type="submit"
        className={cn('atlas-f15-override-submit', !isValid || isPending ? 'is-f15-submit-disabled' : '')}
        disabled={!isValid || isPending}
        data-testid="f15-override-submit"
      >
        {isPending ? 'Applying Override…' : 'Apply Override'}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Content component — rendered only when data is available
// ---------------------------------------------------------------------------

function Framework15Content({ data }: { data: Framework15Result }) {
  const addOverrideMutation = useAddOverride();
  const reviewOrderMutation = useReviewPausedOrder();

  const f15Status = data.f15_status;
  const spikeDisplay = formatVix(data.spike_size);
  const thresholdDisplay = formatVix(data.spike_threshold);
  const currentVixDisplay = formatVix(data.current_vix);
  const sessionOpenDisplay = formatVix(data.session_open_vix);

  const spikeHighlight =
    data.f15_active === true
      ? 'is-f15-spike-active'
      : data.f15_active === null
        ? 'is-f15-spike-unknown'
        : undefined;

  function handleReviewOrder(orderId: number, decision: string) {
    reviewOrderMutation.mutate({
      orderId,
      body: { decision, reviewed_by: 'operator' },
    });
  }

  function handleOverrideSubmit(reason: string, restoreTypes: string[]) {
    addOverrideMutation.mutate({
      override_reason: reason,
      restore_order_types: restoreTypes,
    });
  }

  return (
    <div className="atlas-f15-content" data-testid="f15-content">
      {/* ── Section 2: Four stat cards ─────────────────────────────────── */}
      <div className="atlas-f15-stat-grid" data-testid="f15-stat-grid">
        <StatCard
          label="Session Open VIX"
          value={sessionOpenDisplay}
          highlight={data.session_open_vix === null ? 'is-f15-data-missing' : undefined}
        />
        <StatCard
          label="Current VIX"
          value={currentVixDisplay}
          highlight={data.current_vix === null ? 'is-f15-data-missing' : undefined}
        />
        <StatCard
          label="Spike Size"
          value={spikeDisplay !== '—' ? `+${spikeDisplay}` : '—'}
          highlight={spikeHighlight}
        />
        <StatCard
          label="Threshold"
          value={thresholdDisplay !== '—' ? `+${thresholdDisplay}` : '—'}
        />
      </div>

      {/* ── Section 3: Status panel ─────────────────────────────────────── */}
      <div
        className={cn('atlas-f15-status-panel', STATUS_PANEL_CLASS[f15Status])}
        data-testid="f15-status-panel"
      >
        {f15Status === 'ACTIVE' && (
          <>
            <p className="atlas-f15-status-headline">
              VIX spike of <strong>{spikeDisplay} points</strong> exceeded threshold of{' '}
              <strong>{thresholdDisplay} points</strong>.
              {data.severity && (
                <> Severity: <strong>{data.severity}</strong>.</>
              )}
              {data.halt_triggered_at && (
                <> Halt triggered at {data.halt_triggered_at}.</>
              )}
            </p>
            <div className="atlas-f15-action-chips" data-testid="f15-action-chips">
              <ActionChip label="New Market Orders" blocked={data.new_market_orders_blocked} />
              <ActionChip label="Non-Stop Orders" blocked={data.non_stop_orders_paused} />
              <ActionChip label="Limit Orders" blocked={data.limit_orders_flagged} />
            </div>
          </>
        )}

        {f15Status === 'CLEAR' && (
          <p className="atlas-f15-status-headline">
            VIX within normal range — session open:{' '}
            <strong>{sessionOpenDisplay}</strong>, current:{' '}
            <strong>{currentVixDisplay}</strong>. No halt active.
          </p>
        )}

        {f15Status === 'UNKNOWN' && (
          <p className="atlas-f15-status-headline">
            VIX data unavailable.
            {!data.polygon_available && ' Polygon.io feed offline.'}
            {!data.regime_available && ' Framework 2 regime unavailable.'}
            {' '}Orders blocked for safety.
          </p>
        )}

        {f15Status === 'OUTSIDE_HOURS' && (
          <p className="atlas-f15-status-headline">
            Outside trading hours. F15 evaluation paused until next session open.
          </p>
        )}
      </div>

      {/* ── Section 4: Paused orders (only when halt active) ───────────── */}
      {data.f15_active === true && data.paused_orders.length > 0 && (
        <div className="atlas-f15-paused-orders" data-testid="f15-paused-orders">
          <h4 className="atlas-f15-section-heading">
            Paused Orders ({data.paused_orders_count})
          </h4>
          <table className="atlas-f15-orders-table">
            <thead>
              <tr>
                <th className="atlas-f15-order-th">Ticker</th>
                <th className="atlas-f15-order-th">Type</th>
                <th className="atlas-f15-order-th">Paused At</th>
                <th className="atlas-f15-order-th">Status</th>
                <th className="atlas-f15-order-th">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.paused_orders.map((order) => (
                <PausedOrderRow
                  key={order.order_id}
                  order={order}
                  onReview={handleReviewOrder}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Section 5: Override panel (halt active, no override yet) ───── */}
      {data.f15_active === true && !data.override_active && (
        <div className="atlas-f15-override-panel" data-testid="f15-override-panel">
          <h4 className="atlas-f15-section-heading">Human Override</h4>
          <p className="atlas-f15-override-warning">
            ⚠ Override does not clear the halt alert. It only allows specified
            order types to proceed for this session.
          </p>
          <OverrideForm
            onSubmit={handleOverrideSubmit}
            isPending={addOverrideMutation.isPending}
          />
          {addOverrideMutation.isError && (
            <p className="atlas-f15-override-error" data-testid="f15-override-error">
              Override failed: {addOverrideMutation.error?.message ?? 'Unknown error'}
            </p>
          )}
        </div>
      )}

      {/* ── Section 5b: Override already applied ──────────────────────── */}
      {data.override_active && (
        <div className="atlas-f15-override-applied" data-testid="f15-override-applied">
          <span className="atlas-f15-override-badge">OVERRIDE APPLIED</span>
          {data.override_reason && (
            <p className="atlas-f15-override-reason">
              Reason: {data.override_reason}
            </p>
          )}
        </div>
      )}

      {/* ── Section 6: Framework 25 impact ─────────────────────────────── */}
      <div className="atlas-f15-f25-section" data-testid="f15-f25-section">
        <h4 className="atlas-f15-section-heading">Framework 25 — Liquidity Impact</h4>
        <div className="atlas-f15-f25-row">
          <span className="atlas-f15-f25-label">Current VIX:</span>
          <span className="atlas-f15-f25-value">{currentVixDisplay}</span>
        </div>
        {data.f15_active === true && (
          <p className="atlas-f15-f25-note">
            F25 Liquidity Protocol is receiving a live VIX spike signal from F15.
            Thin-market order rules apply.
          </p>
        )}
      </div>

      {/* ── Section 7: Data source badges ──────────────────────────────── */}
      <div className="atlas-f15-sources" data-testid="f15-sources">
        <DataSourceBadge label="POLYGON" available={data.polygon_available} />
        <DataSourceBadge label="F2 REGIME" available={data.regime_available} />
      </div>

      {/* ── Warnings ───────────────────────────────────────────────────── */}
      {data.warning_messages.length > 0 && (
        <ul className="atlas-f15-warnings" data-testid="f15-warnings">
          {data.warning_messages.map((w, i) => (
            <li key={i} className="atlas-f15-warning-item">
              {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main card
// ---------------------------------------------------------------------------

export function Framework15Card(_props: Framework15CardProps) {
  const { data, isLoading, isError } = useFramework15();

  const f15Status = data?.f15_status ?? 'UNKNOWN';
  const marketOpen = data?.market_open ?? false;

  return (
    <div
      className={cn(
        'atlas-f15-card',
        data ? STATUS_CHIP_CLASS[f15Status] : 'is-f15-loading',
      )}
      data-testid="f15-card"
    >
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="atlas-f15-header" data-testid="f15-header">
        <div className="atlas-f15-header-left">
          <h3 className="atlas-f15-title">Framework 15 — VIX Regime Override</h3>
          <span
            className={cn('atlas-f15-status-chip', data ? STATUS_CHIP_CLASS[f15Status] : '')}
            data-testid="f15-status-chip"
          >
            {data ? STATUS_LABEL[f15Status] : 'LOADING…'}
          </span>
        </div>
        <div className="atlas-f15-header-right">
          {data && (
            <span
              className={cn(
                'atlas-f15-live-indicator',
                marketOpen ? 'is-f15-live' : 'is-f15-closed',
              )}
              data-testid="f15-live-indicator"
            >
              {marketOpen ? 'Live — updates every 60s' : 'Market closed'}
            </span>
          )}
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      {isLoading && (
        <div className="atlas-f15-loading" data-testid="f15-loading">
          Loading VIX data…
        </div>
      )}

      {isError && !data && (
        <div className="atlas-f15-error" data-testid="f15-error">
          Failed to load Framework 15 data.
        </div>
      )}

      {data && <Framework15Content data={data} />}
    </div>
  );
}
