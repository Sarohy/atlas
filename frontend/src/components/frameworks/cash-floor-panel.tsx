'use client';

import { useCashFloor } from '@/lib/hooks/use-cash-floor';
import type { CashFloorResponse } from '@/lib/schemas/cash-floor';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type CashFloorPanelProps = {
  /** Active ticker driven by the shared selector above the panels. */
  ticker: string;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 5 — Cash Floor panel.
 *
 * Reads the live Framework 2 (Regime Modifier) rule and displays the
 * minimum cash reserve the investor must hold against the ticker position.
 */
export function CashFloorPanel({ ticker }: CashFloorPanelProps) {
  const activeTicker = ticker.trim().length > 0;

  const { data, isLoading, isError, error } = useCashFloor(ticker);

  const hasData = activeTicker && data !== undefined;
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
        {!isLoading && !isError && hasData && (
          <CashFloorContent data={data} />
        )}
        {!isLoading && !isError && !hasData && activeTicker && (
          <p className="atlas-fws-state-msg" data-testid="cash-floor-empty">
            No cash floor data available for {ticker}.
          </p>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Content component
// ---------------------------------------------------------------------------

function CashFloorContent({ data }: { data: CashFloorResponse }) {
  const floorMinPct = Math.round(data.floor_pct_min * 100);
  const floorMaxPct = Math.round(data.floor_pct_max * 100);
  const isSymmetric = floorMinPct === floorMaxPct;

  const floorRangeLabel = isSymmetric
    ? `${floorMinPct}% (permanent)`
    : `${floorMinPct}% – ${floorMaxPct}%`;

  return (
    <div className="atlas-cash-floor-content" data-testid="cash-floor-content">
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

      {/* Cash floor details block */}
      <div className="atlas-regime-cash-block">
        <p className="atlas-regime-cash-title">CASH FLOOR REQUIREMENT</p>

        <div className="atlas-regime-cash-row" data-testid="cash-floor-range-row">
          <span className="atlas-regime-cash-label">Floor Range</span>
          <span
            className="atlas-regime-cash-value"
            data-testid="cash-floor-range-value"
          >
            {floorRangeLabel}
          </span>
        </div>

        {data.position_value_usd !== null && (
          <div className="atlas-regime-cash-row" data-testid="cash-floor-position-row">
            <span className="atlas-regime-cash-label">Position Value</span>
            <span className="atlas-regime-cash-value" data-testid="cash-floor-position-value">
              ${data.position_value_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
        )}

        {data.floor_usd_min !== null && (
          <div className="atlas-regime-cash-row" data-testid="cash-floor-min-row">
            <span className="atlas-regime-cash-label">Min Floor (USD)</span>
            <span
              className="atlas-regime-cash-value"
              data-testid="cash-floor-min-value"
            >
              ${data.floor_usd_min.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
        )}

        {data.floor_usd_max !== null && !isSymmetric && (
          <div className="atlas-regime-cash-row" data-testid="cash-floor-max-row">
            <span className="atlas-regime-cash-label">Max Floor (USD)</span>
            <span
              className="atlas-regime-cash-value"
              data-testid="cash-floor-max-value"
            >
              ${data.floor_usd_max.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
        )}

        {data.position_value_usd === null && (
          <div className="atlas-regime-cash-row">
            <span className="atlas-regime-cash-label">USD amounts</span>
            <span className="atlas-regime-cash-value atlas-cash-floor-no-position">
              Not in portfolio
            </span>
          </div>
        )}
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
