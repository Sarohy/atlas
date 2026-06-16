'use client';

import { cn } from '@/lib/utils';
import { useOptionsFlow } from '@/lib/hooks/use-options-flow';
import type { OptionsFlowResponse } from '@/lib/schemas/options-flow';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

const SCORE_BAR_SEGMENTS = 10;

// F4 final-display range. F1 weights F4 at 15% of the 0-100 composite,
// so the panel surfaces a 0-15 "contribution" alongside the raw 0-100 score.
const F4_DISPLAY_MAX = 15;

const GRADE_TONE: Record<string, string> = {
  'STRONG BUY': 'is-green',
  BUY: 'is-cyan',
  NEUTRAL: 'is-yellow',
  WEAK: 'is-orange',
  AVOID: 'is-red',
};

const DIRECTION_TONE: Record<string, string> = {
  BULLISH: 'is-green',
  BEARISH: 'is-red',
  NEUTRAL: 'is-muted',
};

const TIER_TONE: Record<string, string> = {
  LARGE: 'is-cyan',
  MID: 'is-yellow',
  SMALL: 'is-muted',
};

const SOURCE_LABEL: Record<string, string> = {
  BOTH: 'Dark pool + options',
  DARK_POOL_ONLY: 'Dark pool only',
  OPTIONS_ONLY: 'Options flow',
  DATA_GAP: 'Data gap',
};

// Layer 2 — stock-tape state ("chip"). A state, not a score.
const CHIP_LABEL: Record<string, string> = {
  FRESH_ACCUMULATION: 'Fresh Accumulation',
  PERSISTENT_ACCUMULATION: 'Persistent Accumulation',
  NEUTRAL_MIXED: 'Neutral / Mixed',
  FADING: 'Fading',
  ACTIVE_DISTRIBUTION: 'Active Distribution',
  UNKNOWN: 'No tape data',
};
const CHIP_TONE: Record<string, string> = {
  FRESH_ACCUMULATION: 'is-green',
  PERSISTENT_ACCUMULATION: 'is-green',
  NEUTRAL_MIXED: 'is-muted',
  FADING: 'is-orange',
  ACTIVE_DISTRIBUTION: 'is-red',
  UNKNOWN: 'is-muted',
};

// Layer 3 — clearance (the entry decision).
const CLEARANCE_TONE: Record<string, string> = {
  CLEARED: 'is-green',
  WATCH: 'is-yellow',
  REVOKED: 'is-red',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

type F4OptionsPanelProps = {
  /** Active ticker symbol chosen by the shared selector in FrameworksPanelsSection. */
  ticker: string;
};

/**
 * F4 Options Flow panel (v2) — shows F4's signed-net-flow scoring:
 *
 *   • Dark-pool net flow ($) and its 0-100 sub-score
 *   • Options net flow ($) and its 0-100 sub-score
 *   • Market-cap tier (LARGE / MID / SMALL)
 *   • Source label (BOTH / DARK_POOL_ONLY / OPTIONS_ONLY / DATA_GAP)
 *   • 5-session rolling lookback label
 *   • Final F4 score (0-100) + contribution to F1 (0-15)
 *
 * Data source: Unusual Whales (dark pool, option trades) + Polygon (market cap).
 */
export function F4OptionsPanel({ ticker }: F4OptionsPanelProps) {
  const { data, isFetching, isError, error } = useOptionsFlow(ticker);

  return (
    <section className="atlas-frameworks-panel atlas-f4-panel" data-testid="f4-options-panel">
      <header className="atlas-frameworks-panel-header atlas-f4-panel-header">
        <h2 className="atlas-frameworks-panel-title">F4 Options Flow Persistence</h2>
      </header>

      <div className="atlas-f4-panel-body">
        {isFetching && <LoadingState />}
        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Failed to load options flow data.'}
          />
        )}
        {!isFetching && !isError && data && <OptionsFlowContent data={data} />}
        {!isFetching && !isError && !data && ticker && <EmptyState ticker={ticker} />}
      </div>
    </section>
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
  const directionTone = DIRECTION_TONE[data.flow_direction] ?? 'is-muted';
  const tierTone = TIER_TONE[data.market_cap_tier] ?? 'is-muted';
  const sourceLabel = SOURCE_LABEL[data.data_source] ?? data.data_source;
  const contribution = Math.round((data.f4_score / 100) * F4_DISPLAY_MAX);
  const chipTone = CHIP_TONE[data.dark_pool_state] ?? 'is-muted';
  const chipLabel = CHIP_LABEL[data.dark_pool_state] ?? data.dark_pool_state;
  const clearanceTone = CLEARANCE_TONE[data.clearance] ?? 'is-yellow';

  return (
    <div className="atlas-f4-content" data-testid="f4-content">
      {/* Score hero — F4 is the options-flow score (resume) */}
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
          <span className="atlas-f4-label-sub">options flow · {contribution}/{F4_DISPLAY_MAX} to F1</span>
        </div>
      </div>

      {/* Clearance (the entry decision) + stock-tape chip (this week) */}
      <div className="atlas-f4-signal-row">
        <span
          className={cn('atlas-frameworks-pill atlas-f4-grade-pill', clearanceTone)}
          data-testid="f4-clearance"
        >
          {data.clearance}
        </span>
        <span
          className={cn('atlas-frameworks-pill atlas-f4-tier-pill', chipTone)}
          data-testid="f4-dark-pool-state"
        >
          {chipLabel}
        </span>
      </div>
      {data.clearance_reason && (
        <p className="atlas-f4-state-msg" data-testid="f4-clearance-reason">
          {data.clearance_reason}
        </p>
      )}

      {/* Direction + tier + source row */}
      <div className="atlas-f4-signal-row">
        <span
          className={cn('atlas-frameworks-pill atlas-f4-tier-pill', directionTone)}
          data-testid="f4-flow-direction"
        >
          {data.flow_direction}
        </span>
        <span
          className={cn('atlas-frameworks-pill atlas-f4-tier-pill', tierTone)}
          data-testid="f4-market-cap-tier"
        >
          {data.market_cap_tier} CAP
        </span>
        <span
          className="atlas-frameworks-pill atlas-f4-tier-pill is-muted"
          data-testid="f4-data-source"
        >
          {sourceLabel}
        </span>
        <span
          className="atlas-frameworks-pill atlas-f4-tier-pill is-muted"
          data-testid="f4-lookback"
        >
          {data.lookback_sessions}-session rolling
        </span>
      </div>

      {data.data_gap_reason && (
        <p className="atlas-f4-state-msg atlas-f4-state-msg--warn" data-testid="f4-data-gap-reason">
          {data.data_gap_reason}
        </p>
      )}

      {/* Score bar */}
      <ScoreBar score={data.f4_score} gradeTone={gradeTone} />

      {/* Two sub-score cards */}
      <div className="atlas-f4-indicators">
        <DarkPoolFlowCard
          score={data.dark_pool_score}
          netFlow={data.dark_pool_net_flow_usd}
          printsCount={data.dark_pool_prints_count}
          largeBuyCount={data.dark_pool_large_buy_count}
          largestBuy={data.largest_dark_pool_buy_usd}
        />
        <OptionsFlowCard
          score={data.options_flow_score}
          netFlow={data.options_net_flow_usd}
          largestBuy={data.largest_options_buy_usd}
        />
      </div>

      <p className="atlas-f4-state-msg" data-testid="f4-firewall-note">
        F4 scores options flow only (F4b). Dark pool / equity accumulation (F4a) is
        overlay &amp; confirmation — it does not feed the score (SPEC v2.2).
      </p>

      {data.dark_pool_state_reason && (
        <p className="atlas-f4-state-msg" data-testid="f4-dark-pool-state-reason">
          Stock tape (overlay): {data.dark_pool_state_reason}
        </p>
      )}

      {data.market_cap_usd !== null && (
        <p className="atlas-f4-state-msg" data-testid="f4-market-cap">
          Market cap: {formatBigUsd(data.market_cap_usd)}
        </p>
      )}
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
// Sub-score cards
// ---------------------------------------------------------------------------

type SubCardShellProps = {
  label: string;
  testIdSlug: string;
  score: number | null;
  /** True only for the SCORED stream (options/F4b). The overlay stream (F4a)
   *  shows an "overlay · not scored" tag instead of a /100 — the v2.2 firewall. */
  scored: boolean;
  children: React.ReactNode;
};

function SubCardShell({ label, testIdSlug, score, scored, children }: SubCardShellProps) {
  return (
    <article className="atlas-f4-indicator" data-testid={`f4-indicator-${testIdSlug}`}>
      <header className="atlas-f4-indicator-header">
        <span className="atlas-f4-indicator-label">{label}</span>
        {scored ? (
          <span className="atlas-f4-indicator-score">
            {score !== null ? score : '—'}
            <span className="atlas-f4-indicator-max">/100</span>
          </span>
        ) : (
          <span
            className="atlas-frameworks-pill atlas-f4-tier-pill is-muted"
            data-testid={`f4-indicator-${testIdSlug}-overlay-tag`}
          >
            overlay · not scored
          </span>
        )}
      </header>
      <div className="atlas-f4-indicator-body">{children}</div>
    </article>
  );
}

type DarkPoolFlowCardProps = {
  score: number | null;
  netFlow: number | null;
  printsCount: number;
  largeBuyCount: number;
  largestBuy: number | null;
};

function DarkPoolFlowCard({
  score,
  netFlow,
  printsCount,
  largeBuyCount,
  largestBuy,
}: DarkPoolFlowCardProps) {
  return (
    <SubCardShell label="Dark Pool · Equity Accum (F4a)" testIdSlug="dark-pool" score={score} scored={false}>
      <dl className="atlas-f4-dl">
        <div className="atlas-f4-dl-row">
          <dt>Net Flow</dt>
          <dd className={netFlowTone(netFlow)} data-testid="f4-dark-pool-net-flow">
            {netFlow !== null ? formatSignedMillions(netFlow) : '—'}
          </dd>
        </div>
        <div className="atlas-f4-dl-row">
          <dt>Prints</dt>
          <dd>{printsCount > 0 ? printsCount : '—'}</dd>
        </div>
        <div className="atlas-f4-dl-row">
          <dt>Buys &gt; $1M</dt>
          <dd>{largeBuyCount > 0 ? largeBuyCount : '—'}</dd>
        </div>
        {largestBuy !== null && (
          <div className="atlas-f4-dl-row">
            <dt>Largest Buy</dt>
            <dd className="is-green">{formatMillions(largestBuy)}</dd>
          </div>
        )}
      </dl>
    </SubCardShell>
  );
}

type OptionsFlowCardProps = {
  score: number | null;
  netFlow: number | null;
  largestBuy: number | null;
};

function OptionsFlowCard({ score, netFlow, largestBuy }: OptionsFlowCardProps) {
  return (
    <SubCardShell label="Options Flow (F4b · scored)" testIdSlug="options" score={score} scored={true}>
      <dl className="atlas-f4-dl">
        <div className="atlas-f4-dl-row">
          <dt>Net Flow</dt>
          <dd className={netFlowTone(netFlow)} data-testid="f4-options-net-flow">
            {netFlow !== null ? formatSignedMillions(netFlow) : '—'}
          </dd>
        </div>
        {largestBuy !== null && (
          <div className="atlas-f4-dl-row">
            <dt>Largest Buy</dt>
            <dd className="is-green">{formatMillions(largestBuy)}</dd>
          </div>
        )}
      </dl>
    </SubCardShell>
  );
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatMillions(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function formatSignedMillions(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${formatMillions(Math.abs(value))}`.replace('$$', '$');
}

function formatBigUsd(value: number): string {
  if (value >= 1_000_000_000_000) return `$${(value / 1_000_000_000_000).toFixed(2)}T`;
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  return `$${value.toFixed(0)}`;
}

function netFlowTone(value: number | null): string {
  if (value === null || value === 0) return 'is-muted';
  return value > 0 ? 'is-green' : 'is-red';
}
