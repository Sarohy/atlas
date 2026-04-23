'use client';

import { useFramework7 } from '@/lib/hooks/use-framework7';
import { useLeaps } from '@/lib/hooks/use-leaps';
import { usePositionSizing } from '@/lib/hooks/use-position-sizing';
import type { PositionSizingResponse, PositionTier } from '@/lib/schemas/position-sizing';
import { cn } from '@/lib/utils';

/** Number of segments in the conviction score bar. */
const SCORE_BAR_SEGMENTS = 10;

function tierToTone(tier: PositionTier): string {
  switch (tier) {
    case 'TIER_1':
      return 'is-green';
    case 'TIER_2_GREY':
      return 'is-purple';
    case 'TIER_2':
      return 'is-blue';
    case 'TIER_3':
      return 'is-yellow';
    case 'WATCHLIST':
      return 'is-red';
  }
}

type RegimeGuidancePanelProps = {
  ticker: string;
  /** Framework 1 final score — when provided, passed straight to the
   *  position-sizing endpoint so F3 stays in sync with F1. */
  baseScore?: number;
  /** Framework 14 concentration cap flag — blocks Tier 1 adds when true. */
  concentrationCapActive?: boolean;
  /** Pass false to hold the F3 query until a prerequisite (e.g. F1 score)
   *  is ready. Defaults to true. */
  enabled?: boolean;
};

export function RegimeGuidancePanel({
  ticker,
  baseScore,
  concentrationCapActive,
  enabled = true,
}: RegimeGuidancePanelProps) {
  const activeTicker = ticker.trim().length > 0;
  const { data, isLoading, isError, error } = usePositionSizing(
    ticker,
    baseScore,
    concentrationCapActive,
    enabled,
  );
  const hasData = activeTicker && data !== undefined;
  // Hoist F7 gate status — TanStack Query deduplicates this request since
  // Framework7Card uses the identical query key in the same render tree.
  const { data: gateData } = useFramework7(ticker, baseScore);
  const f7GateActive = gateData?.gate_active ?? false;
  const { data: leapsData } = useLeaps(ticker);
  const leapsEligible: boolean | null = leapsData?.leaps_eligible ?? null;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load framework 3 data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-regime-panel atlas-regime-guidance-panel"
      data-testid="regime-guidance-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 3</h2>
        <span className="atlas-fws-subtitle">Score Action Map</span>
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="regime-guidance-loading">
            Computing action…
          </p>
        )}
        {isError && (
          <p
            className="atlas-fws-state-msg atlas-fws-state-msg--error"
            data-testid="regime-guidance-error"
          >
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && hasData && <ActionContent data={data} f7GateActive={f7GateActive} leapsEligible={leapsEligible} />}
        {!isLoading && !isError && !hasData && activeTicker && (
          <p className="atlas-fws-state-msg" data-testid="regime-guidance-empty">
            No position sizing available for {ticker}.
          </p>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ActionContent({
  data,
  f7GateActive = false,
  leapsEligible = null,
}: {
  data: PositionSizingResponse;
  f7GateActive?: boolean;
  leapsEligible?: boolean | null;
}) {
  const tone = tierToTone(data.tier);
  const filledSegs = Math.round(data.conviction_score / SCORE_BAR_SEGMENTS);

  // TIER_3 fix: backend hardcodes adds_permitted=false for all TIER_3 entries,
  // but the correct value is true when no blocking condition exists. F7 gate
  // is the only blocking condition available at this layer.
  const addsPermitted =
    data.tier === 'TIER_3' ? !f7GateActive : data.adds_permitted;

  // TIER_3 fix: override the backend display_message with corrected guidance.
  const displayMessage =
    data.tier === 'TIER_3'
      ? addsPermitted
        ? 'Small position only — max 0.5% NAV. Satellite sizing.'
        : 'Adds blocked — F7 earnings gate active.'
      : data.display_message;

  return (
    <div className="atlas-regime-content" data-testid="regime-guidance-content">
      <div className="atlas-regime-rule-row" data-testid="regime-guidance-rule-row">
        <span
          className={cn('atlas-regime-rule-badge', tone)}
          data-testid="regime-guidance-action-badge"
        >
          POSITION ACTION
        </span>
      </div>

      <div className="atlas-regime-score-hero">
        <div className="atlas-regime-score-block">
          <span className="atlas-regime-score-label">ACTION</span>
          <span
            className={cn('atlas-regime-action-label', tone)}
            data-testid="regime-guidance-action-value"
          >
            {data.action}
          </span>
        </div>
      </div>

      <div
        className="atlas-fws-score-bar"
        aria-label={`Conviction score: ${data.conviction_score} out of 100`}
      >
        {Array.from({ length: SCORE_BAR_SEGMENTS }).map((_, index) => (
          <span
            key={index}
            className={cn('atlas-fws-score-seg', index < filledSegs ? tone : 'is-empty')}
          />
        ))}
      </div>

      {data.grey_zone && <GreyZoneBox consensusConfirmed={data.consensus_confirmed} />}

      <div className="atlas-regime-cash-block" data-testid="regime-guidance-score-block">
        <p className="atlas-regime-cash-title">POSITION DETAILS</p>
        <div className="atlas-regime-cash-row">
          <span className="atlas-regime-cash-label">LEAPS eligible</span>
          <span
            className={cn(
              'atlas-regime-cash-value',
              leapsEligible === true
                ? 'is-active'
                : leapsEligible === false
                  ? 'is-blocked'
                  : 'is-waiting',
            )}
          >
            {leapsEligible === true ? 'Yes' : leapsEligible === false ? 'No' : '—'}
          </span>
        </div>
        <div className="atlas-regime-cash-row">
          <span className="atlas-regime-cash-label">Adds permitted</span>
          <span className="atlas-regime-cash-value">{addsPermitted ? 'Yes' : 'No'}</span>
        </div>
      </div>

      <div className="atlas-regime-output" data-testid="regime-guidance-output-text">
        <p className="atlas-regime-output-line">{displayMessage}</p>
      </div>

      {data.trigger_exit_rules && (
        <p className="atlas-fws-state-msg" data-testid="regime-guidance-exit-rules-note">
          Exit rules active — see Framework 16.
        </p>
      )}
    </div>
  );
}

function GreyZoneBox({ consensusConfirmed }: { consensusConfirmed: boolean }) {
  return (
    <div
      className="atlas-regime-cash-block"
      data-testid="regime-guidance-grey-zone-box"
      style={{ borderColor: 'var(--atlas-purple, #a78bfa)' }}
    >
      <p className="atlas-regime-cash-title">GREY ZONE — 3-MODEL CONSENSUS</p>
      <div className="atlas-regime-cash-row">
        <span className="atlas-regime-cash-label">Consensus confirmed</span>
        <span
          className={cn('atlas-regime-cash-value', consensusConfirmed ? 'is-green' : 'is-red')}
          data-testid="regime-guidance-consensus-status"
        >
          {consensusConfirmed ? 'Yes' : 'Pending'}
        </span>
      </div>
    </div>
  );
}
