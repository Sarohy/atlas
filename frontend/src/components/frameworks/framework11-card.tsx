'use client';

import { cn } from '@/lib/utils';
import { useFramework11 } from '@/lib/hooks/use-framework11';
import { refreshFramework11 } from '@/lib/api/framework11';
import type { F11FloorStatus, Framework11Result, GTCItem } from '@/lib/schemas/framework11';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** GTC proximity threshold below which a GTC is considered near-money (%). */
const GTC_PROXIMITY_THRESHOLD_PCT = 8;

/** GTC window safety buffer multiplier (must match backend). */
const GTC_WINDOW_BUFFER_MULTIPLIER = 1.1;

/** Floor status chip labels. */
const FLOOR_STATUS_LABEL: Record<F11FloorStatus, string> = {
  COMPLIANT: 'FLOOR SATISFIED',
  VIOLATED: 'FLOOR VIOLATED',
  UNKNOWN: 'STATUS UNKNOWN',
};

/** Floor status chip CSS classes. */
const FLOOR_STATUS_CHIP_CLASS: Record<F11FloorStatus, string> = {
  COMPLIANT: 'is-f11-compliant',
  VIOLATED: 'is-f11-violated',
  UNKNOWN: 'is-f11-unknown',
};

/** Props for this portfolio-level card — no ticker required. */
export type Framework11CardProps = Record<string, never>;

// ---------------------------------------------------------------------------
// Pure formatting helpers
// ---------------------------------------------------------------------------

function formatUsd(val: number | null): string {
  if (val === null) return '—';
  if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
  return `$${val.toFixed(0)}`;
}

function formatPct(val: number | null, decimals = 1): string {
  if (val === null) return '—';
  return `${val.toFixed(decimals)}%`;
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
    <div className="atlas-f11-stat-card">
      <span className="atlas-f11-stat-label">{label}</span>
      <span className={cn('atlas-f11-stat-value', highlight ?? '')}>{value}</span>
    </div>
  );
}

function DataSourceBadge({ label, available }: { label: string; available: boolean }) {
  return (
    <span
      className={cn(
        'atlas-f11-source-badge',
        available ? 'is-f11-source-online' : 'is-f11-source-offline',
      )}
      data-testid={`f11-source-${label.toLowerCase().replace(/\s/g, '-')}`}
    >
      {label}: {available ? 'ONLINE' : 'OFFLINE'}
    </span>
  );
}

function GTCRow({ item }: { item: GTCItem }) {
  const rowClass = item.price_missing
    ? 'is-f11-gtc-price-missing'
    : item.is_near_money
      ? 'is-f11-gtc-near-money'
      : 'is-f11-gtc-exempt';

  const proximityDisplay = item.price_missing
    ? '?'
    : item.proximity_pct !== null
      ? `${item.proximity_pct.toFixed(1)}%`
      : '—';

  const statusLabel = item.price_missing
    ? 'PRICE MISSING'
    : item.is_near_money
      ? 'NEAR-MONEY'
      : 'EXEMPT';

  return (
    <tr className={cn('atlas-f11-gtc-row', rowClass)} data-testid={`f11-gtc-row-${item.ticker}`}>
      <td className="atlas-f11-gtc-cell">{item.ticker}</td>
      <td className="atlas-f11-gtc-cell">${item.limit_price.toFixed(2)}</td>
      <td className="atlas-f11-gtc-cell">{item.quantity.toLocaleString()}</td>
      <td className="atlas-f11-gtc-cell">{formatUsd(item.notional_usd)}</td>
      <td className="atlas-f11-gtc-cell">
        {item.current_price !== null ? `$${item.current_price.toFixed(2)}` : '—'}
      </td>
      <td className="atlas-f11-gtc-cell">{proximityDisplay}</td>
      <td className="atlas-f11-gtc-cell">{statusLabel}</td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Content component — rendered only when data is available
// ---------------------------------------------------------------------------

function Framework11Content({ data }: { data: Framework11Result }) {
  const floorPctDisplay = formatPct(data.floor_pct);
  const cashPctDisplay = formatPct(data.cash_pct);
  const cashUsdDisplay = formatUsd(data.cash_usd);
  const navDisplay = formatUsd(data.current_nav);

  const shortfallOrBufferLabel = data.floor_status === 'VIOLATED' ? 'Shortfall' : 'Buffer';
  const shortfallOrBufferValue =
    data.floor_status === 'VIOLATED' ? formatUsd(data.shortfall_usd) : formatUsd(data.buffer_usd);
  const shortfallHighlight =
    data.floor_status === 'VIOLATED' ? 'is-f11-shortfall' : 'is-f11-buffer';

  const gtcWindowDisplay = formatUsd(data.gtc_window_usd);

  const hasGtcOrders = data.gtc_items.length > 0;

  return (
    <div className="atlas-f11-content" data-testid="f11-content">
      {/* ── Section 2: Four stat cards ─────────────────────────────────── */}
      <div className="atlas-f11-stat-grid" data-testid="f11-stat-grid">
        <StatCard
          label="Cash Balance"
          value={data.cash_usd !== null ? cashUsdDisplay : '—'}
          highlight={data.cash_usd === null ? 'is-f11-data-missing' : undefined}
        />
        <StatCard
          label="Cash % of NAV"
          value={data.cash_pct !== null ? cashPctDisplay : '—'}
          highlight={
            data.cash_pct === null
              ? 'is-f11-data-missing'
              : data.floor_status === 'VIOLATED'
                ? 'is-f11-violated-value'
                : 'is-f11-compliant-value'
          }
        />
        <StatCard
          label="Required Floor %"
          value={floorPctDisplay}
          highlight={data.using_conservative_default ? 'is-f11-conservative' : undefined}
        />
        <StatCard
          label={shortfallOrBufferLabel}
          value={shortfallOrBufferValue}
          highlight={shortfallHighlight}
        />
      </div>

      {/* ── Section 3: Floor status panel ──────────────────────────────── */}
      <div
        className={cn(
          'atlas-f11-status-panel',
          data.floor_status === 'COMPLIANT'
            ? 'is-f11-panel-compliant'
            : data.floor_status === 'VIOLATED'
              ? 'is-f11-panel-violated'
              : 'is-f11-panel-unknown',
        )}
        data-testid="f11-status-panel"
      >
        {data.floor_status === 'COMPLIANT' && (
          <>
            <p className="atlas-f11-panel-title">Cash floor satisfied.</p>
            <p className="atlas-f11-panel-line">
              Cash {cashPctDisplay} above {floorPctDisplay} floor. Buffer:{' '}
              {formatUsd(data.buffer_usd)}
            </p>
            <p className="atlas-f11-panel-detail">
              Regime: {data.regime ?? 'Unknown'} → Floor: {floorPctDisplay}
            </p>
            {data.regime?.toUpperCase().includes('CLEAR') &&
              data.clear_transition_days !== null && (
                <p className="atlas-f11-panel-detail">
                  {data.clear_transition_days <= 14
                    ? `CLEAR day ${data.clear_transition_days} of 14 — floor ${floorPctDisplay} (drops to 8% after day 14)`
                    : `CLEAR day ${data.clear_transition_days} — settled floor (8%)`}
                </p>
              )}
          </>
        )}

        {data.floor_status === 'VIOLATED' && (
          <>
            <p className="atlas-f11-panel-title is-f11-violated-title">CASH FLOOR VIOLATED</p>
            <p className="atlas-f11-panel-line">
              Cash {cashPctDisplay} below {floorPctDisplay} floor.
            </p>
            <p className="atlas-f11-panel-line">Shortfall: {formatUsd(data.shortfall_usd)}</p>
            <p className="atlas-f11-panel-line">
              All buy signals queued. Restore cash via sells or distributions.
            </p>
            {data.queued_signals_count > 0 && (
              <p className="atlas-f11-panel-detail is-f11-queued-note">
                {data.queued_signals_count} signal
                {data.queued_signals_count !== 1 ? 's' : ''} queued — pending cash restoration
              </p>
            )}
          </>
        )}

        {data.floor_status === 'UNKNOWN' && (
          <>
            <p className="atlas-f11-panel-title is-f11-unknown-title">Cannot verify floor</p>
            {!data.f30_available && (
              <p className="atlas-f11-panel-line">
                NAV unavailable — cannot determine floor status. Verify manually before any buy.
              </p>
            )}
            {!data.cash_db_available && (
              <p className="atlas-f11-panel-line">
                Cash balance unavailable — cannot verify floor compliance. No buys permitted until
                cash data is restored.
              </p>
            )}
            <p className="atlas-f11-panel-detail">All buys blocked as precaution.</p>
          </>
        )}

        {data.using_conservative_default && (
          <p className="atlas-f11-panel-conservative" data-testid="f11-conservative-note">
            Using conservative {floorPctDisplay} floor — regime data unavailable.
          </p>
        )}
      </div>

      {/* ── Section 4: Regime and floor detail ─────────────────────────── */}
      <div className="atlas-f11-detail-grid" data-testid="f11-detail-grid">
        <div className="atlas-f11-detail-row">
          <span className="atlas-f11-detail-label">Regime</span>
          <span className="atlas-f11-detail-value">{data.regime ?? 'Unknown'}</span>
        </div>
        <div className="atlas-f11-detail-row">
          <span className="atlas-f11-detail-label">Floor source</span>
          <span className="atlas-f11-detail-value">{data.floor_pct_source}</span>
        </div>
        <div className="atlas-f11-detail-row">
          <span className="atlas-f11-detail-label">Floor %</span>
          <span className="atlas-f11-detail-value">{floorPctDisplay}</span>
        </div>
        <div className="atlas-f11-detail-row">
          <span className="atlas-f11-detail-label">Days in CLEAR</span>
          <span className="atlas-f11-detail-value">
            {data.clear_transition_days !== null ? `${data.clear_transition_days}` : 'N/A'}
          </span>
        </div>
        <div className="atlas-f11-detail-row">
          <span className="atlas-f11-detail-label">Portfolio NAV</span>
          <span className="atlas-f11-detail-value">{navDisplay}</span>
        </div>
      </div>

      {/* ── Section 5: GTC aggregate window ────────────────────────────── */}
      <div className="atlas-f11-section" data-testid="f11-gtc-window-section">
        <h4 className="atlas-f11-section-title">GTC Aggregate Window</h4>
        <p className="atlas-f11-formula">
          Window = Cash − ({GTC_WINDOW_BUFFER_MULTIPLIER}× Floor × NAV)
        </p>

        {data.gtc_window_usd !== null &&
          data.cash_usd !== null &&
          data.floor_pct !== null &&
          data.current_nav !== null && (
            <p className="atlas-f11-formula-expanded">
              {formatUsd(data.cash_usd)} − ({GTC_WINDOW_BUFFER_MULTIPLIER} × {floorPctDisplay} ×{' '}
              {navDisplay}) = {gtcWindowDisplay}
            </p>
          )}

        {data.gtc_window_usd === null ? (
          <div
            className="atlas-f11-gtc-panel is-f11-gtc-unknown"
            data-testid="f11-gtc-window-unknown"
          >
            GTC window unknown — {!data.f30_available ? 'NAV' : 'cash balance'} unavailable.
          </div>
        ) : data.gtc_window_negative ? (
          <div
            className="atlas-f11-gtc-panel is-f11-gtc-danger"
            data-testid="f11-gtc-window-negative"
          >
            Window: $0 — GTC unsafe. Cannot hold near-money GTCs.
          </div>
        ) : data.gtc_oversubscribed ? (
          <div
            className="atlas-f11-gtc-panel is-f11-gtc-danger"
            data-testid="f11-gtc-oversubscribed"
          >
            <p className="atlas-f11-panel-title is-f11-violated-title">
              GTC OVERSUBSCRIBED by {formatUsd(data.gtc_excess_usd)}
            </p>
            <p className="atlas-f11-panel-line">
              Near-money GTCs: {formatUsd(data.gtc_near_money_total_usd)}
            </p>
            <p className="atlas-f11-panel-line">Window: {gtcWindowDisplay}</p>
            <p className="atlas-f11-panel-line">Reduce shares or raise cash.</p>
          </div>
        ) : (
          <div className="atlas-f11-gtc-panel is-f11-gtc-ok" data-testid="f11-gtc-ok">
            <p className="atlas-f11-panel-line">GTC within window.</p>
            <p className="atlas-f11-panel-line">
              Near-money: {formatUsd(data.gtc_near_money_total_usd)}
            </p>
            <p className="atlas-f11-panel-line">
              Remaining window: {formatUsd(data.gtc_remaining_usd)}
            </p>
          </div>
        )}
      </div>

      {/* ── Section 6: GTC orders table ────────────────────────────────── */}
      <div className="atlas-f11-section" data-testid="f11-gtc-table-section">
        <h4 className="atlas-f11-section-title">
          Open GTC Buy Orders
          <span className="atlas-f11-gtc-counts">
            Near-money: {data.gtc_near_money_count} | Exempt: {data.gtc_exempt_count} | Price
            missing: {data.gtc_price_missing_count}
          </span>
        </h4>

        {!data.gtc_db_available && (
          <p className="atlas-f11-warning-item" data-testid="f11-gtc-db-unavailable">
            GTC order database unavailable — proximity check incomplete.
          </p>
        )}

        {hasGtcOrders ? (
          <table className="atlas-f11-gtc-table" data-testid="f11-gtc-table">
            <thead>
              <tr>
                <th className="atlas-f11-gtc-th">Ticker</th>
                <th className="atlas-f11-gtc-th">Limit</th>
                <th className="atlas-f11-gtc-th">Qty</th>
                <th className="atlas-f11-gtc-th">Notional</th>
                <th className="atlas-f11-gtc-th">Current Price</th>
                <th className="atlas-f11-gtc-th">
                  Proximity % (≤{GTC_PROXIMITY_THRESHOLD_PCT}% = near)
                </th>
                <th className="atlas-f11-gtc-th">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.gtc_items.map((item) => (
                <GTCRow key={`${item.ticker}-${item.limit_price}`} item={item} />
              ))}
            </tbody>
          </table>
        ) : (
          <p className="atlas-f11-no-orders" data-testid="f11-no-gtc-orders">
            No open GTC buy orders.
          </p>
        )}
      </div>

      {/* ── Section 7: Queued signals ───────────────────────────────────── */}
      {data.queued_signals_count > 0 && (
        <div className="atlas-f11-section atlas-f11-queue-section" data-testid="f11-queue-section">
          <h4 className="atlas-f11-section-title is-f11-queue-title">
            {data.queued_signals_count} signal
            {data.queued_signals_count !== 1 ? 's' : ''} queued pending cash floor restoration
          </h4>
          <ul className="atlas-f11-queue-list">
            {data.signal_queue.map((sig) => {
              const ticker = typeof sig['ticker'] === 'string' ? (sig['ticker'] as string) : '—';
              const action = typeof sig['action'] === 'string' ? (sig['action'] as string) : '—';
              const score = typeof sig['score'] === 'number' ? (sig['score'] as number) : null;
              const queuedAt =
                typeof sig['queued_at'] === 'string' ? (sig['queued_at'] as string) : null;
              return (
                <li
                  key={
                    typeof sig['id'] === 'number' ? (sig['id'] as number) : `${ticker}-${queuedAt}`
                  }
                  className="atlas-f11-queue-item"
                >
                  {ticker} — {action}
                  {score !== null ? ` — Score ${score}` : ''}
                  {queuedAt ? ` — Queued ${new Date(queuedAt).toLocaleTimeString()}` : ''}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* ── Warning messages ────────────────────────────────────────────── */}
      {data.warning_messages.length > 0 && (
        <div className="atlas-f11-warnings" data-testid="f11-warnings">
          {data.warning_messages.map((msg, i) => (
            <p key={i} className="atlas-f11-warning-item">
              {msg}
            </p>
          ))}
        </div>
      )}

      {/* ── Section 8: Data source status ──────────────────────────────── */}
      <div className="atlas-f11-sources" data-testid="f11-sources">
        <DataSourceBadge label="F2 Regime" available={data.f2_available} />
        <DataSourceBadge label="F30 NAV" available={data.f30_available} />
        <DataSourceBadge label="Cash DB" available={data.cash_db_available} />
        <DataSourceBadge label="GTC DB" available={data.gtc_db_available} />
        <span className="atlas-f11-source-age">
          Last updated:{' '}
          {data.data_age_minutes === 0 ? 'just now' : `${data.data_age_minutes} min ago`}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main exported component
// ---------------------------------------------------------------------------

export function Framework11Card() {
  const { data, isLoading, isError } = useFramework11();

  const hasData = data !== undefined;

  async function handleRefresh() {
    try {
      await refreshFramework11();
    } catch {
      // Silently fail — next poll will pick up fresh data.
    }
  }

  return (
    <div className="atlas-f11-card atlas-framework-card" data-testid="framework11-card">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="atlas-f11-header">
        <div className="atlas-f11-header-left">
          <h2 className="atlas-frameworks-panel-title">Framework 11</h2>
          <span className="atlas-fws-subtitle">Cash Floor Enforcer</span>
        </div>
        <div className="atlas-f11-header-right">
          {hasData && (
            <span
              className={cn('atlas-f11-status-chip', FLOOR_STATUS_CHIP_CLASS[data.floor_status])}
              data-testid="f11-status-chip"
            >
              {FLOOR_STATUS_LABEL[data.floor_status]}
            </span>
          )}
          <button
            className="atlas-f11-refresh-btn"
            onClick={handleRefresh}
            aria-label="Refresh Framework 11"
            data-testid="f11-refresh-btn"
          >
            ↺
          </button>
        </div>
      </div>

      {/* ── Loading ─────────────────────────────────────────────────────── */}
      {isLoading && (
        <div className="atlas-f11-loading" data-testid="f11-loading">
          Evaluating cash floor…
        </div>
      )}

      {/* ── Error ───────────────────────────────────────────────────────── */}
      {isError && !isLoading && (
        <div className="atlas-f11-error" data-testid="f11-error">
          Framework 11 data unavailable. All buys blocked as precaution.
        </div>
      )}

      {/* ── Content ─────────────────────────────────────────────────────── */}
      {!isLoading && !isError && hasData && <Framework11Content data={data} />}
    </div>
  );
}
