'use client';

import { useConvictionAction } from '@/lib/hooks/use-conviction-action';
import type { ConvictionActionResponse } from '@/lib/schemas/conviction-action';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** CSS tone → class mapping. */
const TONE_CLASS: Record<string, string> = {
  green: 'is-green',
  cyan: 'is-cyan',
  yellow: 'is-yellow',
  orange: 'is-orange',
  red: 'is-red',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type ConvictionActionPanelProps = {
  /** Active ticker driven by the shared selector above the panels. */
  ticker: string;
  /**
   * The score already displayed by the F1 panel: `final_score + regime_modifier`
   * clamped to 0–100. Passed directly to the backend so the regime delta is
   * not applied a second time.
   */
  adjustedScore: number | undefined;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 6 — Conviction Action panel.
 *
 * Maps the regime-adjusted Framework Score to one of five conviction tiers
 * and shows the investor the recommended status and action lines.
 */
export function ConvictionActionPanel({ ticker, adjustedScore }: ConvictionActionPanelProps) {
  const activeTicker = ticker.trim().length > 0;
  const { data, isLoading, isError, error } = useConvictionAction(ticker, adjustedScore);
  const hasData = activeTicker && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load conviction data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-regime-panel atlas-conviction-panel"
      data-testid="conviction-action-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 6</h2>
        <span className="atlas-fws-subtitle">Score → Conviction Action</span>
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="conviction-loading">
            Computing conviction tier...
          </p>
        )}
        {isError && (
          <p
            className="atlas-fws-state-msg atlas-fws-state-msg--error"
            data-testid="conviction-error"
          >
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && hasData && <ConvictionContent data={data} />}
        {!isLoading && !isError && !hasData && activeTicker && (
          <p className="atlas-fws-state-msg" data-testid="conviction-empty">
            No conviction data available for {ticker}.
          </p>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Content component
// ---------------------------------------------------------------------------

function ConvictionContent({ data }: { data: ConvictionActionResponse }) {
  const toneClass = TONE_CLASS[data.tone] ?? 'is-muted';

  return (
    <div className="atlas-conviction-content" data-testid="conviction-content">
      <p
        className={cn('atlas-conviction-action-label', toneClass)}
        data-testid="conviction-action-label"
      >
        {data.status}
      </p>
    </div>
  );
}
