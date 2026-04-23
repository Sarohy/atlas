'use client';

import React from 'react';

import { cn } from '@/lib/utils';
import { useFramework12 } from '@/lib/hooks/use-framework12';
import { refreshFramework12 } from '@/lib/api/framework12';
import type {
  ActionStatus,
  ActiveCatalyst,
  Framework12Result,
  NoFlyStatus,
  OverrideDetail,
} from '@/lib/schemas/framework12';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** No-fly zone status chip labels. */
const NO_FLY_LABEL: Record<NoFlyStatus, string> = {
  ACTIVE: 'NO-FLY ACTIVE',
  CLEAR: 'CLEAR',
  UNKNOWN: 'STATUS UNKNOWN',
};

/** No-fly zone status chip CSS classes. */
const NO_FLY_CHIP_CLASS: Record<NoFlyStatus, string> = {
  ACTIVE: 'is-f12-active',
  CLEAR: 'is-f12-clear',
  UNKNOWN: 'is-f12-unknown',
};

/** Action status labels. */
const ACTION_STATUS_LABEL: Record<ActionStatus, string> = {
  BLOCKED: 'BLOCKED',
  PERMITTED: 'PERMITTED',
  OVERRIDDEN: 'OVERRIDDEN',
  UNKNOWN: 'UNKNOWN',
};

/** Action status CSS classes. */
const ACTION_STATUS_CLASS: Record<ActionStatus, string> = {
  BLOCKED: 'is-f12-action-blocked',
  PERMITTED: 'is-f12-action-permitted',
  OVERRIDDEN: 'is-f12-action-overridden',
  UNKNOWN: 'is-f12-action-unknown',
};

/** Catalyst type display labels. */
const CATALYST_TYPE_LABEL: Record<string, string> = {
  EARNINGS: 'Earnings',
  INDEX_INCLUSION: 'Index Inclusion',
  PRODUCT_LAUNCH: 'Product Launch',
  PARTNERSHIP: 'Partnership',
  ACQUISITION: 'Acquisition',
  OTHER: 'Other',
};

// ---------------------------------------------------------------------------
// Prop types
// ---------------------------------------------------------------------------

export type Framework12CardProps = {
  /** Active ticker driven by the global ticker selector. */
  ticker: string;
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

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
        'atlas-f12-source-badge',
        available ? 'is-f12-source-online' : 'is-f12-source-offline',
      )}
    >
      {label}: {available ? 'online' : 'offline'}
    </span>
  );
}

function ActionCard({
  label,
  status,
  override,
}: {
  label: string;
  status: ActionStatus;
  override: OverrideDetail | null;
}) {
  return (
    <div className={cn('atlas-f12-action-card', ACTION_STATUS_CLASS[status])}>
      <span className="atlas-f12-action-label">{label}</span>
      <span className="atlas-f12-action-status">
        {ACTION_STATUS_LABEL[status]}
      </span>
      {override !== null && (
        <div className="atlas-f12-override-note">
          <span className="atlas-f12-override-reason">
            Override: {override.override_reason}
          </span>
          <span className="atlas-f12-override-expires">
            Expires: {override.override_expires_at}
          </span>
        </div>
      )}
    </div>
  );
}

function CatalystRow({ catalyst }: { catalyst: ActiveCatalyst }) {
  return (
    <div className="atlas-f12-catalyst-row">
      <span className="atlas-f12-catalyst-type">
        {CATALYST_TYPE_LABEL[catalyst.catalyst_type] ?? catalyst.catalyst_type}
      </span>
      <span className="atlas-f12-catalyst-date">{catalyst.catalyst_date}</span>
      <span className="atlas-f12-catalyst-days">
        {catalyst.days_to_catalyst}d
      </span>
      {catalyst.description !== null && (
        <span className="atlas-f12-catalyst-desc">{catalyst.description}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading / error states
// ---------------------------------------------------------------------------

function Framework12Loading() {
  return (
    <div className="atlas-f12-card">
      <div className="atlas-f12-loading">Loading Framework 12…</div>
    </div>
  );
}

function Framework12Error({ ticker }: { ticker: string }) {
  return (
    <div className="atlas-f12-card">
      <div className="atlas-f12-error">
        Failed to load Framework 12 for {ticker}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main body
// ---------------------------------------------------------------------------

function Framework12Body({
  data,
  ticker,
  onRefresh,
  refreshing,
}: {
  data: Framework12Result;
  ticker: string;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  return (
    <div className="atlas-f12-card">
      {/* ── Section 1: Header ─────────────────────────────────────────── */}
      <div className="atlas-f12-header">
        <div className="atlas-f12-header-left">
          <span className="atlas-f12-label">FR-12 · {ticker}</span>
          <h2 className="atlas-f12-title">Framework 12</h2>
          <span className="atlas-f12-subtitle">Catalyst No-Fly Zone</span>
        </div>
        <div className="atlas-f12-header-right">
          <span
            className={cn(
              'atlas-f12-status-chip',
              NO_FLY_CHIP_CLASS[data.no_fly_status],
            )}
          >
            {NO_FLY_LABEL[data.no_fly_status]}
          </span>
          <button
            aria-label="Refresh Framework 12"
            className="atlas-f12-refresh-btn"
            disabled={refreshing}
            type="button"
            onClick={onRefresh}
          >
            {refreshing ? '…' : '↺'}
          </button>
        </div>
      </div>

      {/* ── Section 2: Status panel ──────────────────────────────────── */}
      {data.no_fly_active === true && data.nearest_catalyst !== null && (
        <div className="atlas-f12-status-panel is-f12-panel-blocked">
          <p className="atlas-f12-panel-title">No-Fly Zone Active</p>
          <p className="atlas-f12-panel-line">
            Nearest catalyst:{' '}
            <strong>
              {CATALYST_TYPE_LABEL[data.nearest_catalyst.catalyst_type] ??
                data.nearest_catalyst.catalyst_type}
            </strong>{' '}
            on <strong>{data.nearest_catalyst.catalyst_date}</strong> (
            {data.nearest_catalyst.days_to_catalyst}d) · window:{' '}
            {data.catalyst_window_days} calendar days
          </p>
        </div>
      )}

      {data.no_fly_active === false && (
        <div className="atlas-f12-status-panel is-f12-panel-clear">
          <p className="atlas-f12-panel-title">No Catalyst Within Window</p>
          <p className="atlas-f12-panel-line">
            No catalyst within the {data.catalyst_window_days}-day window — all
            sell-side actions permitted.
          </p>
        </div>
      )}

      {data.no_fly_active === null && (
        <div className="atlas-f12-status-panel is-f12-panel-unknown">
          <p className="atlas-f12-panel-title">Status Unknown</p>
          <p className="atlas-f12-panel-line">
            One or more data sources unavailable — treating as blocked for
            safety.
          </p>
        </div>
      )}

      {/* ── Section 3: Three action cards ───────────────────────────── */}
      <div className="atlas-f12-action-grid">
        <ActionCard
          label="Covered Calls"
          override={data.covered_calls_override}
          status={data.covered_calls_status}
        />
        <ActionCard
          label="Partial Sells"
          override={data.partial_sells_override}
          status={data.partial_sells_status}
        />
        <ActionCard
          label="Trims"
          override={data.trims_override}
          status={data.trims_status}
        />
      </div>

      {/* ── Section 4: Exit rule conflict (only when active) ────────── */}
      {data.exit_rule_deferred && (
        <div className="atlas-f12-exit-deferred-panel">
          <p className="atlas-f12-panel-title">Exit Rule Deferred</p>
          <p className="atlas-f12-panel-line">
            Section 16 exit window deferred — resumes{' '}
            <strong>{data.exit_deferral_trading_days}</strong> trading days
            after catalyst.{' '}
            {data.exit_rule_deferred_until !== null && (
              <>
                Earliest resume date:{' '}
                <strong>{data.exit_rule_deferred_until}</strong>.
              </>
            )}
          </p>
        </div>
      )}

      {/* ── Section 5: Active catalyst list ─────────────────────────── */}
      {data.active_catalysts.length > 0 && (
        <div className="atlas-f12-catalyst-section">
          <p className="atlas-f12-section-heading">
            Active Catalysts ({data.active_catalysts.length})
          </p>
          {data.active_catalysts.map((c) => (
            <CatalystRow
              key={`${c.catalyst_type}-${c.catalyst_date}`}
              catalyst={c}
            />
          ))}
        </div>
      )}

      {/* ── Section 6: Warnings ──────────────────────────────────────── */}
      {data.warning_messages.length > 0 && (
        <div className="atlas-f12-warnings">
          {data.warning_messages.map((w) => (
            <p key={w} className="atlas-f12-warning-line">
              ⚠ {w}
            </p>
          ))}
        </div>
      )}

      {/* ── Section 7: Data source badges + last updated ────────────── */}
      <div className="atlas-f12-footer">
        <div className="atlas-f12-source-badges">
          <DataSourceBadge available={data.f7_available} label="F7" />
          <DataSourceBadge
            available={data.catalyst_db_available}
            label="Catalyst DB"
          />
          <DataSourceBadge
            available={data.section16_available}
            label="Section 16"
          />
        </div>
        <span className="atlas-f12-last-updated">
          {data.cache_hit ? '⚡ cached' : '🔄 live'} · {data.last_updated}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export function Framework12Card({ ticker }: Framework12CardProps) {
  const { data, isLoading, isError } = useFramework12(ticker);
  const [refreshing, setRefreshing] = React.useState(false);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshFramework12(ticker);
    } finally {
      setRefreshing(false);
    }
  }

  if (isLoading) return <Framework12Loading />;
  if (isError || data === undefined)
    return <Framework12Error ticker={ticker} />;

  return (
    <Framework12Body
      data={data}
      refreshing={refreshing}
      ticker={ticker}
      onRefresh={handleRefresh}
    />
  );
}
