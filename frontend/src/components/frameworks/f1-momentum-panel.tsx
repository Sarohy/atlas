'use client';

import { useState } from 'react';

import { cn } from '@/lib/utils';
import { useMomentum } from '@/lib/hooks/use-momentum';
import { useTickers } from '@/lib/hooks/use-tickers';
import type {
  MacdIndicator,
  MaAlignmentIndicator,
  MomentumResponse,
  PerformanceIndicator,
  RsiIndicator,
  SectorMomentumIndicator,
  Week52PositionIndicator,
} from '@/lib/schemas/momentum';

// ---------------------------------------------------------------------------
// Named constants — UI labels and score thresholds
// ---------------------------------------------------------------------------

/** Number of score bar segments that represent the full scale (0-100). */
const SCORE_BAR_SEGMENTS = 10;

/** Map F1 grade string to CSS tone class name used across the design system. */
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
 * F1 Momentum panel — fetches the user's portfolio tickers from the backend,
 * lets the user pick one from a dropdown, then calls the momentum API and
 * shows RSI, MACD, MA alignment, 52-week position, 1M/6M performance,
 * sector momentum, and the composite F1 score.
 */
export function F1MomentumPanel() {
  const { data: tickerList, isLoading: tickersLoading, isError: tickersError } = useTickers();

  // Derive a sorted list of unique ticker symbols from the portfolio.
  const tickers: string[] = (tickerList ?? []).map((t) => t.ticker).sort();

  const [selectedTicker, setSelectedTicker] = useState<string>('');

  // Resolve the ticker actually used for the API call: prefer the user's
  // explicit choice, but fall back to the first portfolio ticker so the
  // panel is populated automatically on first load.
  const activeTicker = selectedTicker !== '' ? selectedTicker : (tickers[0] ?? '');

  const { data, isFetching, isError, error } = useMomentum(activeTicker);

  return (
    <section className="atlas-frameworks-panel atlas-f1-panel" data-testid="f1-momentum-panel">
      <header className="atlas-frameworks-panel-header atlas-f1-panel-header">
        <h2 className="atlas-frameworks-panel-title">F1 Momentum</h2>
        {tickersLoading && (
          <span className="atlas-f1-state-msg" data-testid="f1-tickers-loading">
            Loading tickers…
          </span>
        )}
        {tickersError && (
          <span
            className="atlas-f1-state-msg atlas-f1-state-msg--error"
            data-testid="f1-tickers-error"
          >
            Failed to load portfolio tickers.
          </span>
        )}
        {!tickersLoading && !tickersError && tickers.length > 0 && (
          <TickerSelect tickers={tickers} value={activeTicker} onChange={setSelectedTicker} />
        )}
      </header>

      <div className="atlas-f1-panel-body">
        {isFetching && <LoadingState />}
        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Failed to load momentum data.'}
          />
        )}
        {!isFetching && !isError && data && <MomentumContent data={data} />}
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
      className="atlas-f1-ticker-select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Select ticker for F1 momentum analysis"
      data-testid="f1-ticker-select"
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
    <p className="atlas-f1-state-msg" data-testid="f1-loading">
      Calculating momentum…
    </p>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="atlas-f1-state-msg atlas-f1-state-msg--error" data-testid="f1-error">
      {message}
    </p>
  );
}

function EmptyState({ ticker }: { ticker: string }) {
  return (
    <p className="atlas-f1-state-msg" data-testid="f1-empty">
      No momentum data available for {ticker}.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main content — rendered when data is available
// ---------------------------------------------------------------------------

function MomentumContent({ data }: { data: MomentumResponse }) {
  const gradeTone = GRADE_TONE[data.f1_grade] ?? 'is-yellow';

  return (
    <div className="atlas-f1-content" data-testid="f1-content">
      {/* F1 Score hero */}
      <div className="atlas-f1-score-hero">
        <div className="atlas-f1-score-ring">
          <span className={cn('atlas-f1-score-number', gradeTone)} data-testid="f1-score">
            {data.f1_score}
          </span>
          <span className="atlas-f1-score-denom">/100</span>
        </div>
        <div className="atlas-f1-score-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-f1-grade-pill', gradeTone)}
            data-testid="f1-grade"
          >
            {data.f1_grade}
          </span>
          <span className="atlas-f1-sector-etf">vs {data.sector_etf}</span>
        </div>
      </div>

      {/* Score bar */}
      <ScoreBar score={data.f1_score} gradeTone={gradeTone} />

      {/* Indicator grid */}
      <div className="atlas-f1-indicators">
        <RsiCard rsi={data.rsi} />
        <MacdCard macd={data.macd} />
        <MaCard ma={data.ma_alignment} />
        <Week52Card w52={data.week_52_position} />
        <PerfCard perf={data.performance} />
        <SectorCard sector={data.sector_momentum} />
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
      className="atlas-f1-score-bar"
      role="progressbar"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {Array.from({ length: SCORE_BAR_SEGMENTS }, (_, i) => (
        <span
          key={i}
          className={cn('atlas-f1-score-bar-seg', i < filled ? gradeTone : 'is-empty')}
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
      className="atlas-f1-indicator"
      data-testid={`f1-indicator-${label.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <header className="atlas-f1-indicator-header">
        <span className="atlas-f1-indicator-label">{label}</span>
        <span className="atlas-f1-indicator-score">
          {score}
          <span className="atlas-f1-indicator-max">/{maxScore}</span>
        </span>
      </header>
      <div className="atlas-f1-indicator-body">{children}</div>
    </article>
  );
}

function RsiCard({ rsi }: { rsi: RsiIndicator }) {
  return (
    <IndicatorCard label="RSI" score={rsi.score} maxScore={rsi.max_score}>
      <dl className="atlas-f1-dl">
        <div className="atlas-f1-dl-row">
          <dt>RSI (14)</dt>
          <dd className={rsiTone(rsi.value)}>{rsi.value !== null ? rsi.value.toFixed(1) : '—'}</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>Zone</dt>
          <dd>{rsiZoneLabel(rsi.value)}</dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function MacdCard({ macd }: { macd: MacdIndicator }) {
  const isPositive = macd.histogram >= 0;
  return (
    <IndicatorCard label="MACD" score={macd.score} maxScore={macd.max_score}>
      <dl className="atlas-f1-dl">
        <div className="atlas-f1-dl-row">
          <dt>MACD</dt>
          <dd>{macd.macd_line.toFixed(3)}</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>Signal</dt>
          <dd>{macd.signal_line.toFixed(3)}</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>Histogram</dt>
          <dd className={isPositive ? 'is-green' : 'is-red'}>
            {macd.histogram >= 0 ? '+' : ''}
            {macd.histogram.toFixed(3)}
          </dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function MaCard({ ma }: { ma: MaAlignmentIndicator }) {
  return (
    <IndicatorCard label="MA Alignment" score={ma.score} maxScore={ma.max_score}>
      <dl className="atlas-f1-dl">
        <div className="atlas-f1-dl-row">
          <dt>Alignment</dt>
          <dd className={maAlignmentTone(ma.label)}>{ma.label.replace('_', ' ')}</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>MA 20</dt>
          <dd>{formatPrice(ma.ma_20)}</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>MA 50</dt>
          <dd>{formatPrice(ma.ma_50)}</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>MA 200</dt>
          <dd>{formatPrice(ma.ma_200)}</dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function Week52Card({ w52 }: { w52: Week52PositionIndicator }) {
  return (
    <IndicatorCard label="52-Week Position" score={w52.score} maxScore={w52.max_score}>
      <dl className="atlas-f1-dl">
        <div className="atlas-f1-dl-row">
          <dt>Position</dt>
          <dd className={week52Tone(w52.position_pct)}>{w52.position_pct.toFixed(1)}%</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>52W High</dt>
          <dd>{formatPrice(w52.high_52w)}</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>52W Low</dt>
          <dd>{formatPrice(w52.low_52w)}</dd>
        </div>
      </dl>
      {/* Mini range bar */}
      <div className="atlas-f1-range-bar">
        <span
          className={cn('atlas-f1-range-bar-fill', week52Tone(w52.position_pct))}
          style={{ width: `${w52.position_pct}%` }}
        />
      </div>
    </IndicatorCard>
  );
}

function PerfCard({ perf }: { perf: PerformanceIndicator }) {
  return (
    <IndicatorCard label="Performance" score={perf.score} maxScore={perf.max_score}>
      <dl className="atlas-f1-dl">
        <div className="atlas-f1-dl-row">
          <dt>1 Month</dt>
          <dd className={perfTone(perf.perf_1m)}>
            {formatPct(perf.perf_1m)}
            <span className="atlas-f1-sub-score"> ({perf.score_1m}/10)</span>
          </dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>6 Month</dt>
          <dd className={perfTone(perf.perf_6m)}>
            {formatPct(perf.perf_6m)}
            <span className="atlas-f1-sub-score"> ({perf.score_6m}/10)</span>
          </dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function SectorCard({ sector }: { sector: SectorMomentumIndicator }) {
  return (
    <IndicatorCard label="Sector Momentum" score={sector.score} maxScore={sector.max_score}>
      <dl className="atlas-f1-dl">
        <div className="atlas-f1-dl-row">
          <dt>Sector ETF</dt>
          <dd>{sector.sector_etf}</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>Ticker 3M</dt>
          <dd className={perfTone(sector.ticker_perf_3m)}>{formatPct(sector.ticker_perf_3m)}</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>Sector 3M</dt>
          <dd>{formatPct(sector.sector_perf_3m)}</dd>
        </div>
        <div className="atlas-f1-dl-row">
          <dt>Relative</dt>
          <dd className={perfTone(sector.relative_perf_3m)}>
            {sector.relative_perf_3m >= 0 ? '+' : ''}
            {formatPct(sector.relative_perf_3m)}
          </dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

// ---------------------------------------------------------------------------
// Small formatting helpers — pure, no side effects
// ---------------------------------------------------------------------------

function formatPrice(value: number): string {
  return value > 0 ? `$${value.toFixed(2)}` : '—';
}

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function rsiTone(value: number | null): string {
  if (value === null) return '';
  if (value >= 60 && value < 80) return 'is-green';
  if (value >= 50) return 'is-cyan';
  if (value < 30) return 'is-red';
  return 'is-yellow';
}

function rsiZoneLabel(value: number | null): string {
  if (value === null) return '—';
  if (value >= 80) return 'Overbought';
  if (value >= 60) return 'Strong';
  if (value >= 50) return 'Moderate';
  if (value >= 40) return 'Weak';
  if (value >= 30) return 'Bearish';
  return 'Oversold';
}

function maAlignmentTone(label: string): string {
  const map: Record<string, string> = {
    FULL_BULL: 'is-green',
    BULL: 'is-cyan',
    MIXED: 'is-yellow',
    BEAR: 'is-orange',
    FULL_BEAR: 'is-red',
  };
  return map[label] ?? '';
}

function week52Tone(pct: number): string {
  if (pct >= 80) return 'is-green';
  if (pct >= 60) return 'is-cyan';
  if (pct >= 40) return 'is-yellow';
  if (pct >= 20) return 'is-orange';
  return 'is-red';
}

function perfTone(pct: number): string {
  if (pct >= 5) return 'is-green';
  if (pct >= 0) return 'is-cyan';
  if (pct >= -5) return 'is-yellow';
  return 'is-red';
}
