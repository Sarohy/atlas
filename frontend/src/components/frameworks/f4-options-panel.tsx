'use client';

import { useState } from 'react';

import { cn } from '@/lib/utils';
import { useOptionsFlow } from '@/lib/hooks/use-options-flow';
import { useTickers } from '@/lib/hooks/use-tickers';
import type {
  CallPutRatioIndicator,
  DarkPoolIndicator,
  OptionsFlowResponse,
  SweepTypeIndicator,
  VolumeOiIndicator,
  WhaleBlockIndicator,
} from '@/lib/schemas/options-flow';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

const SCORE_BAR_SEGMENTS = 10;

const GRADE_TONE: Record<string, string> = {
  'STRONG BUY': 'is-green',
  BUY: 'is-cyan',
  NEUTRAL: 'is-yellow',
  WEAK: 'is-orange',
  AVOID: 'is-red',
};

/** Signal tier badge colours per the signal hierarchy. */
const TIER_TONE: Record<string, string> = {
  GOLD: 'is-gold',
  BLUE: 'is-cyan',
  GREEN: 'is-green',
  YELLOW: 'is-yellow',
  GREY: 'is-muted',
  WHITE: 'is-muted',
  NONE: 'is-muted',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * F4 Options Flow panel — self-contained, no props.
 *
 * Five sub-indicators per Factor_Mapping_Guide:
 *   Whale Block Size (35%) | Call/Put Ratio (20%) | Volume vs OI (20%)
 *   Dark Pool Print (15%) | Sweep Type (10%)
 *
 * Data source: Unusual Whales API.
 * Collar flag caps score at 68 when protective put + covered call structure is detected.
 */
export function F4OptionsPanel() {
  const { data: tickerList, isLoading: tickersLoading, isError: tickersError } = useTickers();
  const tickers: string[] = (tickerList ?? []).map((t) => t.ticker).sort();
  const [selectedTicker, setSelectedTicker] = useState<string>('');
  const activeTicker = selectedTicker !== '' ? selectedTicker : (tickers[0] ?? '');
  const { data, isFetching, isError, error } = useOptionsFlow(activeTicker);

  return (
    <section className="atlas-frameworks-panel atlas-f4-panel" data-testid="f4-options-panel">
      <header className="atlas-frameworks-panel-header atlas-f4-panel-header">
        <h2 className="atlas-frameworks-panel-title">F4 Options Flow</h2>
        {tickersLoading && (
          <span className="atlas-f4-state-msg" data-testid="f4-tickers-loading">
            Loading tickers…
          </span>
        )}
        {tickersError && (
          <span className="atlas-f4-state-msg atlas-f4-state-msg--error" data-testid="f4-tickers-error">
            Failed to load portfolio tickers.
          </span>
        )}
        {!tickersLoading && !tickersError && tickers.length > 0 && (
          <TickerSelect tickers={tickers} value={activeTicker} onChange={setSelectedTicker} />
        )}
      </header>

      <div className="atlas-f4-panel-body">
        {isFetching && <LoadingState />}
        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Failed to load options flow data.'}
          />
        )}
        {!isFetching && !isError && data && <OptionsFlowContent data={data} />}
        {!isFetching && !isError && !data && activeTicker && <EmptyState ticker={activeTicker} />}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Ticker selector
// ---------------------------------------------------------------------------

function TickerSelect({
  tickers,
  value,
  onChange,
}: {
  tickers: readonly string[];
  value: string;
  onChange: (t: string) => void;
}) {
  return (
    <select
      className="atlas-f4-ticker-select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Select ticker for F4 options flow analysis"
      data-testid="f4-ticker-select"
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
    <p className="atlas-f4-state-msg" data-testid="f4-loading">
      Reading options flow…
    </p>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="atlas-f4-state-msg atlas-f4-state-msg--error" data-testid="f4-error">
      {message}
    </p>
  );
}

function EmptyState({ ticker }: { ticker: string }) {
  return (
    <p className="atlas-f4-state-msg" data-testid="f4-empty">
      No options flow data available for {ticker}.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main content
// ---------------------------------------------------------------------------

function OptionsFlowContent({ data }: { data: OptionsFlowResponse }) {
  const gradeTone = GRADE_TONE[data.f4_grade] ?? 'is-yellow';
  const tierTone = TIER_TONE[data.signal_tier] ?? 'is-muted';

  return (
    <div className="atlas-f4-content" data-testid="f4-content">
      {/* Score hero */}
      <div className="atlas-f4-score-hero">
        <div className="atlas-f4-score-ring">
          <span className={cn('atlas-f4-score-number', gradeTone)} data-testid="f4-score">
            {data.f4_score}
          </span>
          <span className="atlas-f4-score-denom">/100</span>
        </div>
        <div className="atlas-f4-score-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-f4-grade-pill', gradeTone)}
            data-testid="f4-grade"
          >
            {data.f4_grade}
          </span>
          <span className="atlas-f4-label-sub">Options Flow</span>
        </div>
      </div>

      {/* Signal tier + collar flag row */}
      <div className="atlas-f4-signal-row">
        <span
          className={cn('atlas-frameworks-pill atlas-f4-tier-pill', tierTone)}
          data-testid="f4-signal-tier"
        >
          {data.signal_tier}
        </span>
        {data.collar_flag && (
          <span
            className="atlas-frameworks-pill atlas-f4-collar-pill is-orange"
            data-testid="f4-collar-flag"
          >
            COLLAR — Capped at 68
          </span>
        )}
      </div>

      {/* Score bar */}
      <ScoreBar score={data.f4_score} gradeTone={gradeTone} />

      {/* Five weighted indicator cards */}
      <div className="atlas-f4-indicators">
        <WhaleBlockCard whale={data.whale_block} />
        <CallPutRatioCard cp={data.call_put_ratio} />
        <VolumeOiCard volOi={data.volume_oi} />
        <DarkPoolCard dp={data.dark_pool} />
        <SweepTypeCard sweep={data.sweep_type} />
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
      className="atlas-f4-score-bar"
      role="progressbar"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {Array.from({ length: SCORE_BAR_SEGMENTS }, (_, i) => (
        <span
          key={i}
          className={cn('atlas-f4-score-bar-seg', i < filled ? gradeTone : 'is-empty')}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Indicator card shell
// ---------------------------------------------------------------------------

function IndicatorCard({
  label,
  score,
  weight,
  children,
}: {
  label: string;
  score: number;
  weight: number;
  children: React.ReactNode;
}) {
  const weightPct = Math.round(weight * 100);
  return (
    <article
      className="atlas-f4-indicator"
      data-testid={`f4-indicator-${label.toLowerCase().replace(/[\s/]+/g, '-')}`}
    >
      <header className="atlas-f4-indicator-header">
        <span className="atlas-f4-indicator-label">{label}</span>
        <div className="atlas-f4-indicator-meta">
          <span className="atlas-f4-indicator-weight">{weightPct}%</span>
          <span className="atlas-f4-indicator-score">
            {score}
            <span className="atlas-f4-indicator-max">/100</span>
          </span>
        </div>
      </header>
      <div className="atlas-f4-indicator-body">{children}</div>
    </article>
  );
}

// ---------------------------------------------------------------------------
// Individual indicator cards
// ---------------------------------------------------------------------------

function WhaleBlockCard({ whale }: { whale: WhaleBlockIndicator }) {
  return (
    <IndicatorCard label="Whale Block Size" score={whale.score} weight={whale.weight}>
      <dl className="atlas-f4-dl">
        <div className="atlas-f4-dl-row">
          <dt>Largest Print</dt>
          <dd className={whaleTone(whale.largest_premium)}>
            {whale.largest_premium !== null ? formatMillions(whale.largest_premium) : '—'}
          </dd>
        </div>
        <div className="atlas-f4-dl-row">
          <dt>Signal</dt>
          <dd>{whaleTierLabel(whale.largest_premium)}</dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function CallPutRatioCard({ cp }: { cp: CallPutRatioIndicator }) {
  return (
    <IndicatorCard label="Call / Put Ratio" score={cp.score} weight={cp.weight}>
      <dl className="atlas-f4-dl">
        <div className="atlas-f4-dl-row">
          <dt>C/P Ratio</dt>
          <dd className={cpTone(cp.ratio)}>
            {cp.ratio !== null ? `${cp.ratio.toFixed(2)}:1` : '—'}
          </dd>
        </div>
        {cp.call_premium !== null && (
          <div className="atlas-f4-dl-row">
            <dt>Call Prem</dt>
            <dd className="is-green">{formatMillions(cp.call_premium)}</dd>
          </div>
        )}
        {cp.put_premium !== null && (
          <div className="atlas-f4-dl-row">
            <dt>Put Prem</dt>
            <dd className="is-red">{formatMillions(cp.put_premium)}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function VolumeOiCard({ volOi }: { volOi: VolumeOiIndicator }) {
  return (
    <IndicatorCard label="Volume vs OI" score={volOi.score} weight={volOi.weight}>
      <dl className="atlas-f4-dl">
        <div className="atlas-f4-dl-row">
          <dt>Vol / OI</dt>
          <dd className={volOiTone(volOi.vol_oi_ratio)}>
            {volOi.vol_oi_ratio !== null ? `${volOi.vol_oi_ratio.toFixed(2)}×` : '—'}
          </dd>
        </div>
        {volOi.call_volume !== null && (
          <div className="atlas-f4-dl-row">
            <dt>Call Vol</dt>
            <dd>{formatCount(volOi.call_volume)}</dd>
          </div>
        )}
        {volOi.call_open_interest !== null && (
          <div className="atlas-f4-dl-row">
            <dt>Call OI</dt>
            <dd>{formatCount(volOi.call_open_interest)}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function DarkPoolCard({ dp }: { dp: DarkPoolIndicator }) {
  return (
    <IndicatorCard label="Dark Pool Print" score={dp.score} weight={dp.weight}>
      <dl className="atlas-f4-dl">
        <div className="atlas-f4-dl-row">
          <dt>Largest Print</dt>
          <dd className={dpTone(dp.largest_print)}>
            {dp.largest_print !== null ? formatMillions(dp.largest_print) : '—'}
          </dd>
        </div>
        {dp.total_dark_pool_premium !== null && (
          <div className="atlas-f4-dl-row">
            <dt>Total DP Vol</dt>
            <dd>{formatMillions(dp.total_dark_pool_premium)}</dd>
          </div>
        )}
        <div className="atlas-f4-dl-row">
          <dt>Print Count</dt>
          <dd>{dp.print_count > 0 ? dp.print_count : '—'}</dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function SweepTypeCard({ sweep }: { sweep: SweepTypeIndicator }) {
  const sweepLabel = sweep.has_golden_sweep
    ? 'Golden Sweep'
    : sweep.has_single_sweep
      ? 'Single Sweep'
      : sweep.has_repeated_hits
        ? 'Repeated Hits'
        : 'No Sweep';

  const sweepTone = sweep.has_golden_sweep
    ? 'is-gold'
    : sweep.has_single_sweep
      ? 'is-cyan'
      : sweep.has_repeated_hits
        ? 'is-green'
        : '';

  return (
    <IndicatorCard label="Sweep Type" score={sweep.score} weight={sweep.weight}>
      <dl className="atlas-f4-dl">
        <div className="atlas-f4-dl-row">
          <dt>Type</dt>
          <dd className={sweepTone} data-testid="f4-sweep-label">
            {sweepLabel}
          </dd>
        </div>
        {sweep.sweep_premium !== null && (
          <div className="atlas-f4-dl-row">
            <dt>Sweep Size</dt>
            <dd>{formatMillions(sweep.sweep_premium)}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatMillions(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function formatCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return value.toFixed(0);
}

// ---------------------------------------------------------------------------
// Tone helpers
// ---------------------------------------------------------------------------

function whaleTone(premium: number | null): string {
  if (premium === null) return '';
  if (premium > 5_000_000) return 'is-green';
  if (premium >= 1_000_000) return 'is-cyan';
  if (premium >= 500_000) return 'is-yellow';
  if (premium >= 100_000) return 'is-orange';
  return 'is-red';
}

function whaleTierLabel(premium: number | null): string {
  if (premium === null) return '—';
  if (premium > 5_000_000) return 'Golden Sweep';
  if (premium >= 1_000_000) return 'Whale Block';
  if (premium >= 500_000) return 'Large Print';
  if (premium >= 100_000) return 'Notable';
  return 'Small';
}

function cpTone(ratio: number | null): string {
  if (ratio === null) return '';
  if (ratio > 3) return 'is-green';
  if (ratio >= 2) return 'is-cyan';
  if (ratio >= 1.5) return 'is-yellow';
  if (ratio >= 0.8) return 'is-orange';
  return 'is-red';
}

function volOiTone(ratio: number | null): string {
  if (ratio === null) return '';
  if (ratio > 5) return 'is-green';
  if (ratio >= 3) return 'is-cyan';
  if (ratio >= 2) return 'is-yellow';
  if (ratio >= 1) return 'is-orange';
  return 'is-red';
}

function dpTone(premium: number | null): string {
  if (premium === null) return '';
  if (premium > 5_000_000) return 'is-green';
  if (premium >= 1_000_000) return 'is-cyan';
  if (premium >= 100_000) return 'is-yellow';
  return '';
}
