'use client';

import { usePositionSizing } from '@/lib/hooks/use-position-sizing';
import { cn } from '@/lib/utils';

const SCORE_BAR_SEGMENTS = 10;

function scoreToTone(score: number): string {
  if (score > 90) return 'is-green';
  if (score >= 80) return 'is-cyan';
  if (score >= 70) return 'is-yellow';
  if (score >= 60) return 'is-orange';
  return 'is-red';
}

type RegimeGuidancePanelProps = {
  ticker: string;
  /** Framework 1 final score — when provided, passed straight to the
   *  position-sizing endpoint so F3 stays in sync with F1. */
  baseScore?: number;
};

export function RegimeGuidancePanel({ ticker, baseScore }: RegimeGuidancePanelProps) {
  const activeTicker = ticker.trim().length > 0;
  const { data, isLoading, isError, error } = usePositionSizing(ticker, baseScore);
  const hasData = activeTicker && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load framework 3 data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-regime-panel atlas-regime-guidance-panel"
      data-testid="regime-guidance-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 3</h2>
        <span className="atlas-fws-subtitle">Conviction {'->'} Position Sizing</span>
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="regime-guidance-loading">
            Fetching position sizing...
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
        {!isLoading && !isError && hasData && (
          <GuidanceContent
            action={data.action}
            convictionScore={data.conviction_score}
            instruction={data.instruction}
          />
        )}
        {!isLoading && !isError && !hasData && activeTicker && (
          <p className="atlas-fws-state-msg" data-testid="regime-guidance-empty">
            No position sizing available for {ticker}.
          </p>
        )}
      </div>
    </section>
  );
}

type GuidanceContentProps = {
  action: string;
  convictionScore: number;
  instruction: string;
};

function GuidanceContent({ action, convictionScore, instruction }: GuidanceContentProps) {
  const tone = scoreToTone(convictionScore);
  const filledSegs = Math.round(convictionScore / SCORE_BAR_SEGMENTS);

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
            className={cn('atlas-regime-score-num', tone)}
            data-testid="regime-guidance-action-value"
          >
            {action}
          </span>
        </div>
      </div>

      <div
        className="atlas-fws-score-bar"
        aria-label={`Conviction score: ${convictionScore} out of 100`}
      >
        {Array.from({ length: SCORE_BAR_SEGMENTS }).map((_, index) => (
          <span
            key={index}
            className={cn('atlas-fws-score-seg', index < filledSegs ? tone : 'is-empty')}
          />
        ))}
      </div>

      <div className="atlas-regime-cash-block" data-testid="regime-guidance-score-block">
        <p className="atlas-regime-cash-title">FRAMEWORK 1 SCORE</p>
        <div className="atlas-regime-cash-row">
          <span className="atlas-regime-cash-label">Conviction score</span>
          <span className="atlas-regime-cash-value" data-testid="regime-guidance-score">
            {convictionScore}
          </span>
        </div>
      </div>

      <div className="atlas-regime-output" data-testid="regime-guidance-output-text">
        <p className="atlas-regime-output-line">{instruction}</p>
      </div>
    </div>
  );
}
