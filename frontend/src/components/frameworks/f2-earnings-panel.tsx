'use client';

import { useState } from 'react';

import { cn } from '@/lib/utils';
import { useEarnings } from '@/lib/hooks/use-earnings';
import { useTickers } from '@/lib/hooks/use-tickers';
import type {
  BacklogBtbIndicator,
  EarningsResponse,
  EpsBeatsIndicator,
  GuidanceIndicator,
  MarginTrajectoryIndicator,
  RevenueGrowthIndicator,
} from '@/lib/schemas/earnings';

// ---------------------------------------------------------------------------
// Named constants — UI labels and score thresholds
// ---------------------------------------------------------------------------

/** Number of score bar segments representing the full 0-100 scale. */
const SCORE_BAR_SEGMENTS = 10;

/** Map F2 grade string to CSS tone class name used across the design system. */
const GRADE_TONE: Record<string, string> = {
  'STRONG BUY': 'is-green',
  BUY: 'is-cyan',
  NEUTRAL: 'is-yellow',
  WEAK: 'is-orange',
  AVOID: 'is-red',
};

/** Human-readable labels for the revision_direction integer. */
const REVISION_LABEL: Record<number, string> = {
  2: 'Consistently Raised',
  1: 'Raised',
  0: 'Flat',
  [-1]: 'Cut',
  [-2]: 'Consistently Cut',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * F2 Earnings Quality panel — fetches the user's portfolio tickers from the
 * backend, lets the user pick one, then calls the earnings API and shows
 * revenue growth, EPS beats, guidance, backlog/BTB, margin trajectory, and
 * the composite F2 score.
 */
export function F2EarningsPanel() {
  const { data: tickerList, isLoading: tickersLoading, isError: tickersError } = useTickers();

  const tickers: string[] = (tickerList ?? []).map((t) => t.ticker).sort();

  const [selectedTicker, setSelectedTicker] = useState<string>('');

  // Resolve the active ticker: prefer explicit selection, fall back to first.
  const activeTicker = selectedTicker !== '' ? selectedTicker : (tickers[0] ?? '');

  const { data, isFetching, isError, error } = useEarnings(activeTicker);

  return (
    <section className="atlas-frameworks-panel atlas-f2-panel" data-testid="f2-earnings-panel">
      <header className="atlas-frameworks-panel-header atlas-f2-panel-header">
        <h2 className="atlas-frameworks-panel-title">F2 Earnings Quality</h2>
        {tickersLoading && (
          <span className="atlas-f2-state-msg" data-testid="f2-tickers-loading">
            Loading tickers…
          </span>
        )}
        {tickersError && (
          <span
            className="atlas-f2-state-msg atlas-f2-state-msg--error"
            data-testid="f2-tickers-error"
          >
            Failed to load portfolio tickers.
          </span>
        )}
        {!tickersLoading && !tickersError && tickers.length > 0 && (
          <TickerSelect tickers={tickers} value={activeTicker} onChange={setSelectedTicker} />
        )}
      </header>

      <div className="atlas-f2-panel-body">
        {isFetching && <LoadingState />}
        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Failed to load earnings data.'}
          />
        )}
        {!isFetching && !isError && data && <EarningsContent data={data} />}
        {!isFetching && !isError && !data && activeTicker && <EmptyState ticker={activeTicker} />}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Ticker selector
// ---------------------------------------------------------------------------

type TickerSelectProps = {
  tickers: readonly string[];
  value: string;
  onChange: (ticker: string) => void;
};

function TickerSelect({ tickers, value, onChange }: TickerSelectProps) {
  return (
    <select
      className="atlas-f2-ticker-select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Select ticker for F2 earnings quality analysis"
      data-testid="f2-ticker-select"
    >
      {tickers.map((t) => (
        <option key={t} value={t}>
          {t}
        </option>
      ))}
    </select>
  );
}

// ---------------------------------------------------------------------------
// State components
// ---------------------------------------------------------------------------

function LoadingState() {
  return (
    <p className="atlas-f2-state-msg" data-testid="f2-loading">
      Analysing earnings quality…
    </p>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="atlas-f2-state-msg atlas-f2-state-msg--error" data-testid="f2-error">
      {message}
    </p>
  );
}

function EmptyState({ ticker }: { ticker: string }) {
  return (
    <p className="atlas-f2-state-msg" data-testid="f2-empty">
      No earnings data available for {ticker}.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main content — rendered when data is available
// ---------------------------------------------------------------------------

function EarningsContent({ data }: { data: EarningsResponse }) {
  const gradeTone = GRADE_TONE[data.f2_grade] ?? 'is-yellow';

  return (
    <div className="atlas-f2-content" data-testid="f2-content">
      {/* F2 Score hero */}
      <div className="atlas-f2-score-hero">
        <div className="atlas-f2-score-ring">
          <span className={cn('atlas-f2-score-number', gradeTone)} data-testid="f2-score">
            {data.f2_score}
          </span>
          <span className="atlas-f2-score-denom">/100</span>
        </div>
        <div className="atlas-f2-score-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-f2-grade-pill', gradeTone)}
            data-testid="f2-grade"
          >
            {data.f2_grade}
          </span>
          <span className="atlas-f2-label-sub">Earnings Quality</span>
        </div>
      </div>

      {/* Score bar */}
      <ScoreBar score={data.f2_score} gradeTone={gradeTone} />

      {/* Indicator grid */}
      <div className="atlas-f2-indicators">
        <RevenueGrowthCard rev={data.revenue_growth} />
        <EpsBeatsCard eps={data.eps_beats} />
        <GuidanceCard guidance={data.guidance} />
        <BacklogBtbCard btb={data.backlog_btb} />
        <MarginTrajectoryCard margin={data.margin_trajectory} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score bar
// ---------------------------------------------------------------------------

function ScoreBar({ score, gradeTone }: { score: number; gradeTone: string }) {
  const filled = Math.round((score / 100) * SCORE_BAR_SEGMENTS);

  return (
    <div
      className="atlas-f2-score-bar"
      role="progressbar"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {Array.from({ length: SCORE_BAR_SEGMENTS }, (_, i) => (
        <span
          key={i}
          className={cn('atlas-f2-score-bar-seg', i < filled ? gradeTone : 'is-empty')}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Indicator cards
// ---------------------------------------------------------------------------

type IndicatorCardProps = {
  label: string;
  score: number;
  maxScore: number;
  children: React.ReactNode;
};

function IndicatorCard({ label, score, maxScore, children }: IndicatorCardProps) {
  return (
    <article
      className="atlas-f2-indicator"
      data-testid={`f2-indicator-${label.toLowerCase().replace(/[\s/]+/g, '-')}`}
    >
      <header className="atlas-f2-indicator-header">
        <span className="atlas-f2-indicator-label">{label}</span>
        <span className="atlas-f2-indicator-score">
          {score}
          <span className="atlas-f2-indicator-max">/{maxScore}</span>
        </span>
      </header>
      <div className="atlas-f2-indicator-body">{children}</div>
    </article>
  );
}

function RevenueGrowthCard({ rev }: { rev: RevenueGrowthIndicator }) {
  return (
    <IndicatorCard label="Revenue Growth" score={rev.score} maxScore={rev.max_score}>
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>YoY Growth</dt>
          <dd className={growthTone(rev.growth_pct)}>
            {rev.growth_pct !== null ? formatPct(rev.growth_pct) : '—'}
          </dd>
        </div>
        {rev.current_ttm !== null && (
          <div className="atlas-f2-dl-row">
            <dt>TTM Revenue</dt>
            <dd>{formatMillions(rev.current_ttm)}</dd>
          </div>
        )}
        {rev.prior_ttm !== null && (
          <div className="atlas-f2-dl-row">
            <dt>Prior TTM</dt>
            <dd>{formatMillions(rev.prior_ttm)}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function EpsBeatsCard({ eps }: { eps: EpsBeatsIndicator }) {
  const beatsLabel = eps.quarters_beat !== null ? `${eps.quarters_beat}/4` : '—';

  return (
    <IndicatorCard label="EPS Beats" score={eps.score} maxScore={eps.max_score}>
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>Beat Rate</dt>
          <dd className={beatRateTone(eps.beat_rate_pct)}>
            {eps.beat_rate_pct !== null ? formatPct(eps.beat_rate_pct) : '—'}
          </dd>
        </div>
        <div className="atlas-f2-dl-row">
          <dt>Quarters Beat</dt>
          <dd>{beatsLabel}</dd>
        </div>
      </dl>
      {eps.beat_rate_pct !== null && (
        <div className="atlas-f2-beat-bar">
          <span
            className={cn('atlas-f2-beat-bar-fill', beatRateTone(eps.beat_rate_pct))}
            style={{ width: `${eps.beat_rate_pct}%` }}
          />
        </div>
      )}
    </IndicatorCard>
  );
}

function GuidanceCard({ guidance }: { guidance: GuidanceIndicator }) {
  const label = REVISION_LABEL[guidance.revision_direction] ?? 'Unknown';
  return (
    <IndicatorCard label="Guidance" score={guidance.score} maxScore={guidance.max_score}>
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>Direction</dt>
          <dd className={guidanceTone(guidance.revision_direction)}>{label}</dd>
        </div>
        {guidance.revision_pct !== null && (
          <div className="atlas-f2-dl-row">
            <dt>EPS Revision</dt>
            <dd className={growthTone(guidance.revision_pct)}>
              {formatPct(guidance.revision_pct)}
            </dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function BacklogBtbCard({ btb }: { btb: BacklogBtbIndicator }) {
  return (
    <IndicatorCard label="Backlog / BTB" score={btb.score} maxScore={btb.max_score}>
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>BTB Proxy</dt>
          <dd className={btbTone(btb.btb_proxy)}>
            {btb.btb_proxy !== null
              ? `${btb.btb_proxy >= 0 ? '+' : ''}${btb.btb_proxy.toFixed(2)}`
              : '—'}
          </dd>
        </div>
        {btb.revenue_acceleration !== null && (
          <div className="atlas-f2-dl-row">
            <dt>Rev. Acceleration</dt>
            <dd className={growthTone(btb.revenue_acceleration)}>
              {btb.revenue_acceleration >= 0 ? '+' : ''}
              {btb.revenue_acceleration.toFixed(2)} ppts
            </dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function MarginTrajectoryCard({ margin }: { margin: MarginTrajectoryIndicator }) {
  return (
    <IndicatorCard label="Margin Trajectory" score={margin.score} maxScore={margin.max_score}>
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>Avg QoQ Change</dt>
          <dd className={marginTone(margin.trajectory)}>
            {margin.trajectory !== null
              ? `${margin.trajectory >= 0 ? '+' : ''}${margin.trajectory.toFixed(2)} ppts`
              : '—'}
          </dd>
        </div>
      </dl>
      {margin.gross_margins.length > 0 && (
        <div className="atlas-f2-margin-sparkline">
          {margin.gross_margins.map((m, i) => (
            <div key={i} className="atlas-f2-margin-bar-wrap">
              <div
                className={cn('atlas-f2-margin-bar', marginBarTone(m))}
                style={{ height: `${Math.min(100, Math.max(5, m))}%` }}
                title={`Q${i + 1}: ${m.toFixed(1)}%`}
              />
              <span className="atlas-f2-margin-bar-label">{m.toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
    </IndicatorCard>
  );
}

// ---------------------------------------------------------------------------
// Small formatting helpers — pure, no side effects
// ---------------------------------------------------------------------------

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function formatMillions(value: number): string {
  if (Math.abs(value) >= 1_000) {
    return `$${(value / 1_000).toFixed(1)}B`;
  }
  return `$${value.toFixed(0)}M`;
}

function growthTone(value: number | null): string {
  if (value === null) return '';
  if (value >= 15) return 'is-green';
  if (value >= 5) return 'is-cyan';
  if (value >= 0) return 'is-yellow';
  return 'is-red';
}

function beatRateTone(pct: number | null): string {
  if (pct === null) return '';
  if (pct >= 75) return 'is-green';
  if (pct >= 50) return 'is-cyan';
  if (pct >= 25) return 'is-yellow';
  return 'is-red';
}

function guidanceTone(direction: number): string {
  if (direction >= 2) return 'is-green';
  if (direction >= 1) return 'is-cyan';
  if (direction === 0) return 'is-yellow';
  if (direction === -1) return 'is-orange';
  return 'is-red';
}

function btbTone(proxy: number | null): string {
  if (proxy === null) return '';
  if (proxy > 5) return 'is-green';
  if (proxy >= 0) return 'is-cyan';
  if (proxy >= -2) return 'is-yellow';
  return 'is-red';
}

function marginTone(trajectory: number | null): string {
  if (trajectory === null) return '';
  if (trajectory >= 0.02) return 'is-green';
  if (trajectory >= 0) return 'is-cyan';
  if (trajectory >= -0.02) return 'is-yellow';
  return 'is-red';
}

function marginBarTone(margin: number): string {
  if (margin >= 40) return 'is-green';
  if (margin >= 25) return 'is-cyan';
  if (margin >= 10) return 'is-yellow';
  return 'is-red';
}
