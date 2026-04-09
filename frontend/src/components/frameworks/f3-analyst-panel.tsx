'use client';

import { useState } from 'react';

import { cn } from '@/lib/utils';
import { useAnalyst } from '@/lib/hooks/use-analyst';
import { useTickers } from '@/lib/hooks/use-tickers';
import type {
  AnalystCoverageIndicator,
  AnalystResponse,
  ConsensusRatingIndicator,
  PtDirectionIndicator,
  PtUpsideIndicator,
  RecentUpgradesIndicator,
} from '@/lib/schemas/analyst';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Number of score bar segments representing the full 0-100 scale. */
const SCORE_BAR_SEGMENTS = 10;

/** Map F3 grade string to CSS tone class name used across the design system. */
const GRADE_TONE: Record<string, string> = {
  'STRONG BUY': 'is-green',
  BUY: 'is-cyan',
  NEUTRAL: 'is-yellow',
  WEAK: 'is-orange',
  AVOID: 'is-red',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * F3 Analyst Conviction panel — self-contained, no props.
 *
 * Fetches the user's portfolio tickers, lets them pick one, then calls the
 * analyst API and renders consensus rating, PT upside, PT direction, analyst
 * coverage, and recent upgrades alongside the composite F3 score.
 */
export function F3AnalystPanel() {
  const { data: tickerList, isLoading: tickersLoading, isError: tickersError } = useTickers();

  const tickers: string[] = (tickerList ?? []).map((t) => t.ticker).sort();

  const [selectedTicker, setSelectedTicker] = useState<string>('');

  // Resolve the active ticker: prefer explicit selection, fall back to first.
  const activeTicker = selectedTicker !== '' ? selectedTicker : (tickers[0] ?? '');

  const { data, isFetching, isError, error } = useAnalyst(activeTicker);

  return (
    <section className="atlas-frameworks-panel atlas-f3-panel" data-testid="f3-analyst-panel">
      <header className="atlas-frameworks-panel-header atlas-f3-panel-header">
        <h2 className="atlas-frameworks-panel-title">F3 Analyst Conviction</h2>
        {tickersLoading && (
          <span className="atlas-f3-state-msg" data-testid="f3-tickers-loading">
            Loading tickers…
          </span>
        )}
        {tickersError && (
          <span
            className="atlas-f3-state-msg atlas-f3-state-msg--error"
            data-testid="f3-tickers-error"
          >
            Failed to load portfolio tickers.
          </span>
        )}
        {!tickersLoading && !tickersError && tickers.length > 0 && (
          <TickerSelect tickers={tickers} value={activeTicker} onChange={setSelectedTicker} />
        )}
      </header>

      <div className="atlas-f3-panel-body">
        {isFetching && <LoadingState />}
        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Failed to load analyst data.'}
          />
        )}
        {!isFetching && !isError && data && <AnalystContent data={data} />}
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
      className="atlas-f3-ticker-select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Select ticker for F3 analyst conviction analysis"
      data-testid="f3-ticker-select"
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
    <p className="atlas-f3-state-msg" data-testid="f3-loading">
      Analysing analyst conviction…
    </p>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="atlas-f3-state-msg atlas-f3-state-msg--error" data-testid="f3-error">
      {message}
    </p>
  );
}

function EmptyState({ ticker }: { ticker: string }) {
  return (
    <p className="atlas-f3-state-msg" data-testid="f3-empty">
      No analyst data available for {ticker}.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main content — rendered when data is available
// ---------------------------------------------------------------------------

function AnalystContent({ data }: { data: AnalystResponse }) {
  const gradeTone = GRADE_TONE[data.f3_grade] ?? 'is-yellow';

  return (
    <div className="atlas-f3-content" data-testid="f3-content">
      {/* F3 Score hero */}
      <div className="atlas-f3-score-hero">
        <div className="atlas-f3-score-ring">
          <span className={cn('atlas-f3-score-number', gradeTone)} data-testid="f3-score">
            {data.f3_score}
          </span>
          <span className="atlas-f3-score-denom">/100</span>
        </div>
        <div className="atlas-f3-score-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-f3-grade-pill', gradeTone)}
            data-testid="f3-grade"
          >
            {data.f3_grade}
          </span>
          <span className="atlas-f3-label-sub">Analyst Conviction</span>
        </div>
      </div>

      {/* Score bar */}
      <ScoreBar score={data.f3_score} gradeTone={gradeTone} />

      {/* Indicator grid */}
      <div className="atlas-f3-indicators">
        <ConsensusRatingCard consensus={data.consensus_rating} />
        <PtUpsideCard pt={data.pt_upside} />
        <PtDirectionCard dir={data.pt_direction} />
        <AnalystCoverageCard coverage={data.analyst_coverage} />
        <RecentUpgradesCard upgrades={data.recent_upgrades} />
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
      className="atlas-f3-score-bar"
      role="progressbar"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {Array.from({ length: SCORE_BAR_SEGMENTS }, (_, i) => (
        <span
          key={i}
          className={cn('atlas-f3-score-bar-seg', i < filled ? gradeTone : 'is-empty')}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Indicator card shell
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
      className="atlas-f3-indicator"
      data-testid={`f3-indicator-${label.toLowerCase().replace(/[\s/]+/g, '-')}`}
    >
      <header className="atlas-f3-indicator-header">
        <span className="atlas-f3-indicator-label">{label}</span>
        <span className="atlas-f3-indicator-score">
          {score}
          <span className="atlas-f3-indicator-max">/{maxScore}</span>
        </span>
      </header>
      <div className="atlas-f3-indicator-body">{children}</div>
    </article>
  );
}

// ---------------------------------------------------------------------------
// Individual indicator cards
// ---------------------------------------------------------------------------

function ConsensusRatingCard({ consensus }: { consensus: ConsensusRatingIndicator }) {
  return (
    <IndicatorCard label="Consensus Rating" score={consensus.score} maxScore={consensus.max_score}>
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Consensus</dt>
          <dd className={consensusTone(consensus.label)} data-testid="f3-consensus-label">
            {consensus.label}
          </dd>
        </div>
        {consensus.buy_pct !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Buy %</dt>
            <dd>{consensus.buy_pct.toFixed(1)}%</dd>
          </div>
        )}
        <div className="atlas-f3-dl-row">
          <dt>B / H / S</dt>
          <dd>
            {consensus.buy_count} / {consensus.hold_count} / {consensus.sell_count}
          </dd>
        </div>
      </dl>
      {consensus.total_analysts > 0 && (
        <div className="atlas-f3-consensus-bar" aria-hidden="true">
          {consensus.buy_count > 0 && (
            <span
              className="atlas-f3-consensus-bar-buy"
              style={{ width: `${(consensus.buy_count / consensus.total_analysts) * 100}%` }}
            />
          )}
          {consensus.hold_count > 0 && (
            <span
              className="atlas-f3-consensus-bar-hold"
              style={{ width: `${(consensus.hold_count / consensus.total_analysts) * 100}%` }}
            />
          )}
          {consensus.sell_count > 0 && (
            <span
              className="atlas-f3-consensus-bar-sell"
              style={{ width: `${(consensus.sell_count / consensus.total_analysts) * 100}%` }}
            />
          )}
        </div>
      )}
    </IndicatorCard>
  );
}

function PtUpsideCard({ pt }: { pt: PtUpsideIndicator }) {
  return (
    <IndicatorCard label="PT Upside" score={pt.score} maxScore={pt.max_score}>
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Upside</dt>
          <dd className={upsideTone(pt.upside_pct)}>
            {pt.upside_pct !== null ? formatPct(pt.upside_pct) : '—'}
          </dd>
        </div>
        {pt.current_price !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Current Price</dt>
            <dd>{formatPrice(pt.current_price)}</dd>
          </div>
        )}
        {pt.consensus_pt !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Consensus PT</dt>
            <dd>{formatPrice(pt.consensus_pt)}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function PtDirectionCard({ dir }: { dir: PtDirectionIndicator }) {
  return (
    <IndicatorCard label="PT Direction" score={dir.score} maxScore={dir.max_score}>
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>PT Change</dt>
          <dd className={directionTone(dir.direction_pct)}>
            {dir.direction_pct !== null ? formatPct(dir.direction_pct) : 'No prior data'}
          </dd>
        </div>
        {dir.current_consensus_pt !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Current PT</dt>
            <dd>{formatPrice(dir.current_consensus_pt)}</dd>
          </div>
        )}
        {dir.prior_consensus_pt !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Prior PT</dt>
            <dd>{formatPrice(dir.prior_consensus_pt)}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function AnalystCoverageCard({ coverage }: { coverage: AnalystCoverageIndicator }) {
  return (
    <IndicatorCard label="Analyst Coverage" score={coverage.score} maxScore={coverage.max_score}>
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Analysts</dt>
          <dd className={coverageTone(coverage.num_analysts)}>
            {coverage.num_analysts > 0 ? coverage.num_analysts : '—'}
          </dd>
        </div>
        <div className="atlas-f3-dl-row">
          <dt>Reliability</dt>
          <dd>{coverageLabel(coverage.num_analysts)}</dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function RecentUpgradesCard({ upgrades }: { upgrades: RecentUpgradesIndicator }) {
  return (
    <IndicatorCard label="Recent Upgrades" score={upgrades.score} maxScore={upgrades.max_score}>
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Net</dt>
          <dd className={netUpgradesTone(upgrades.net_upgrades)}>
            {upgrades.net_upgrades >= 0 ? '+' : ''}
            {upgrades.net_upgrades}
          </dd>
        </div>
        <div className="atlas-f3-dl-row">
          <dt>Upgrades</dt>
          <dd className="is-green">{upgrades.upgrades}</dd>
        </div>
        <div className="atlas-f3-dl-row">
          <dt>Downgrades</dt>
          <dd className={upgrades.downgrades > 0 ? 'is-red' : ''}>{upgrades.downgrades}</dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

// ---------------------------------------------------------------------------
// Formatting and tone helpers — pure, no side effects
// ---------------------------------------------------------------------------

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function formatPrice(value: number): string {
  return `$${value.toFixed(2)}`;
}

function consensusTone(label: string): string {
  if (label === 'STRONG BUY') return 'is-green';
  if (label === 'BUY') return 'is-cyan';
  if (label === 'HOLD') return 'is-yellow';
  if (label === 'UNDERPERFORM') return 'is-orange';
  if (label === 'SELL') return 'is-red';
  return '';
}

function upsideTone(upside: number | null): string {
  if (upside === null) return '';
  if (upside >= 25) return 'is-green';
  if (upside >= 10) return 'is-cyan';
  if (upside >= 0) return 'is-yellow';
  return 'is-red';
}

function directionTone(direction: number | null): string {
  if (direction === null) return '';
  if (direction >= 5) return 'is-green';
  if (direction >= 1) return 'is-cyan';
  if (direction >= -1) return 'is-yellow';
  if (direction >= -5) return 'is-orange';
  return 'is-red';
}

function coverageTone(count: number): string {
  if (count >= 20) return 'is-green';
  if (count >= 10) return 'is-cyan';
  if (count >= 5) return 'is-yellow';
  if (count >= 2) return 'is-orange';
  return 'is-red';
}

function coverageLabel(count: number): string {
  if (count >= 20) return 'High';
  if (count >= 10) return 'Good';
  if (count >= 5) return 'Moderate';
  if (count >= 2) return 'Minimal';
  return 'None';
}

function netUpgradesTone(net: number): string {
  if (net >= 3) return 'is-green';
  if (net >= 1) return 'is-cyan';
  if (net === 0) return 'is-yellow';
  if (net >= -2) return 'is-orange';
  return 'is-red';
}
