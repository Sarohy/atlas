'use client';

import { useFramework5 } from '@/lib/hooks/use-cash-floor';
import type { FloorStatus, Framework5Response } from '@/lib/schemas/cash-floor';

// ---------------------------------------------------------------------------
// Public component — no ticker prop; portfolio-level
// ---------------------------------------------------------------------------

/**
 * Framework 5 — Cash Floor panel.
 *
 * Reads the live Framework 2 regime (Brent + VIX) and displays the
 * portfolio-level minimum cash reserve requirement.
 * No ticker required — the floor applies to the whole portfolio.
 */
export function CashFloorPanel() {
  const { data, isLoading, isError, error } = useFramework5();

  const errorMsg = error instanceof Error ? error.message : 'Failed to load cash floor data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-regime-panel atlas-cash-floor-panel"
      data-testid="cash-floor-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 5</h2>
        <span className="atlas-fws-subtitle">Regime → Cash Floor</span>
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="cash-floor-loading">
            Computing cash floor...
          </p>
        )}
        {isError && (
          <p
            className="atlas-fws-state-msg atlas-fws-state-msg--error"
            data-testid="cash-floor-error"
          >
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && data !== undefined && (
          <CashFloorContent data={data} />
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const USD_FORMAT: Intl.NumberFormatOptions = {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
};

function formatUsd(value: number): string {
  return `$${value.toLocaleString('en-US', USD_FORMAT)}`;
}

/** Human-readable labels for each FloorStatus value. */
const CASH_STATUS_LABELS: Record<FloorStatus, string> = {
  HEALTHY: 'HEALTHY',
  LOW_BUFFER: 'LOW BUFFER',
  AT_FLOOR: 'AT FLOOR',
  BELOW_FLOOR: 'CRITICAL — BELOW FLOOR',
  CRITICAL_ZERO: 'CRITICAL — ZERO CASH',
};

function getCashStatusLabel(status: FloorStatus): string {
  return CASH_STATUS_LABELS[status];
}

/** Pill tone class for each FloorStatus. */
const STATUS_CHIP_TONE: Record<FloorStatus, string> = {
  HEALTHY: 'is-green',
  LOW_BUFFER: 'is-yellow',
  AT_FLOOR: 'is-yellow',
  BELOW_FLOOR: 'is-red',
  CRITICAL_ZERO: 'is-red',
};

/** Pill tone class for regime names returned by the API (space-separated). */
const REGIME_CHIP_TONE: Record<string, string> = {
  CLEAR: 'is-green',
  'SOFT CAUTION': 'is-blue',
  CAUTION: 'is-yellow',
  'CRISIS HALT': 'is-red',
};

// ---------------------------------------------------------------------------
// Content component
// ---------------------------------------------------------------------------

function CashFloorContent({ data }: { data: Framework5Response }) {
  return (
    <div className="atlas-cash-floor-content" data-testid="cash-floor-content">
      {/* Status chips row — two distinct pills: cash status + regime */}
      <div className="atlas-fws-status-row">
        <span
          className={`atlas-frameworks-pill ${STATUS_CHIP_TONE[data.floor_status]}`}
          data-testid="cash-floor-status-chip"
        >
          {getCashStatusLabel(data.floor_status)}
        </span>
        <span
          className={`atlas-frameworks-pill ${REGIME_CHIP_TONE[data.regime] ?? 'is-yellow'}`}
          data-testid="cash-floor-regime-chip"
        >
          {data.regime}
        </span>
      </div>

      {/* Market snapshot */}
      <div className="atlas-regime-market-row">
        <div className="atlas-regime-stat">
          <span className="atlas-regime-stat-label">BRENT</span>
          <span className="atlas-regime-stat-value" data-testid="cash-floor-brent">
            {data.brent_price !== null ? `$${data.brent_price.toFixed(2)}` : '—'}
          </span>
        </div>
        <div className="atlas-regime-stat-divider" />
        <div className="atlas-regime-stat">
          <span className="atlas-regime-stat-label">VIX</span>
          <span className="atlas-regime-stat-value" data-testid="cash-floor-vix">
            {data.vix_value !== null ? data.vix_value.toFixed(2) : '—'}
          </span>
        </div>
      </div>

      {/* Warning box — shown for AMBER and CRITICAL */}
      {data.warning_level !== 'NONE' && data.warning_message && (
        <div
          className={`atlas-fws-warning-box atlas-fws-warning-box--${data.warning_level.toLowerCase()}`}
          data-testid="cash-floor-warning-box"
        >
          <p className="atlas-fws-warning-msg">{data.warning_message}</p>
        </div>
      )}

      {/* Cash floor details */}
      <div className="atlas-regime-cash-block">
        <p className="atlas-regime-cash-title">CASH FLOOR REQUIREMENT</p>

        <div className="atlas-regime-cash-row" data-testid="cash-floor-range-row">
          <span className="atlas-regime-cash-label">Floor</span>
          <span className="atlas-regime-cash-value" data-testid="cash-floor-range-value">
            {data.floor_pct_display}
          </span>
        </div>

        <div className="atlas-regime-cash-row" data-testid="cash-floor-position-row">
          <span className="atlas-regime-cash-label">Total NAV</span>
          <span className="atlas-regime-cash-value" data-testid="cash-floor-position-value">
            {formatUsd(data.total_nav)}
          </span>
        </div>

        <div className="atlas-regime-cash-row" data-testid="cash-floor-min-row">
          <span className="atlas-regime-cash-label">
            Floor Amount ({Math.round(data.floor_pct * 100)}%)
          </span>
          <span className="atlas-regime-cash-value" data-testid="cash-floor-min-value">
            {formatUsd(data.floor_amount)}
          </span>
        </div>

        <div className="atlas-regime-cash-row" data-testid="cash-floor-cash-held-row">
          <span className="atlas-regime-cash-label">Cash Held</span>
          <span className="atlas-regime-cash-value" data-testid="cash-floor-cash-held-value">
            {formatUsd(data.total_cash)}
          </span>
        </div>

        <div className="atlas-regime-cash-row" data-testid="cash-floor-available-row">
          <span className="atlas-regime-cash-label">Available Above Floor</span>
          <span className="atlas-regime-cash-value" data-testid="cash-floor-available-value">
            {formatUsd(data.available_above_floor)}
          </span>
        </div>
      </div>

      {/* Rationale */}
      <div
        className="atlas-regime-output atlas-cash-floor-rationale"
        data-testid="cash-floor-rationale"
      >
        <p className="atlas-regime-output-line">{data.rationale}</p>
      </div>
    </div>
  );
}
