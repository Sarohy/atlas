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

// Headline tone by F4b STATE band (Implementation Audit). The panel headlines the
// state band — never a BUY (a full add only comes from the Flow Monitor).
const STATE_TONE: Record<string, string> = {
  'Strong bullish': 'is-green',
  Bullish: 'is-green',
  'Mild bullish': 'is-cyan',
  Constructive: 'is-cyan',
  'Neutral-constructive': 'is-yellow',
  Neutral: 'is-yellow',
  'Mild bearish': 'is-orange',
  Bearish: 'is-red',
  'Aggressive bearish': 'is-red',
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

// Flow Monitor — the final action gate (the only add authority).
const FLOW_MONITOR_LABEL: Record<string, string> = {
  ADD_ELIGIBLE: 'ADD ELIGIBLE',
  ADD_PENDING_GATES: 'ADD — PENDING GATES',
  STARTER: 'STARTER / WATCH',
  WATCH: 'WATCH / NO FRESH ADD',
  CONFLICT: 'CONFLICT / NO CHASE',
  MIXED_ABSORPTION: 'MIXED ABSORPTION / WATCH',
  TRIM_WATCH: 'TRIM-WATCH',
  AVOID: 'AVOID',
};
const FLOW_MONITOR_TONE: Record<string, string> = {
  ADD_ELIGIBLE: 'is-green',
  ADD_PENDING_GATES: 'is-cyan',
  STARTER: 'is-yellow',
  WATCH: 'is-yellow',
  CONFLICT: 'is-orange',
  MIXED_ABSORPTION: 'is-orange',
  TRIM_WATCH: 'is-red',
  AVOID: 'is-red',
};

// Hedge-structure context flag — tagged separately from the F4 score so a bearish
// reading with protective context is distinguished from raw directional bearishness.
const HEDGE_LABEL: Record<string, string> = {
  DIRECTIONAL_BEARISH: 'Directional bearish',
  PROTECTIVE_HEDGE: 'Protective hedge',
  HEDGED_BULLISH: 'Hedged bullish',
  PUT_SELLING: 'Put selling',
  BULLISH: 'Bullish',
  MIXED: 'Mixed',
  NONE: 'No structure',
};
const HEDGE_TONE: Record<string, string> = {
  DIRECTIONAL_BEARISH: 'is-red',
  PROTECTIVE_HEDGE: 'is-muted',
  HEDGED_BULLISH: 'is-green',
  PUT_SELLING: 'is-green',
  BULLISH: 'is-green',
  MIXED: 'is-muted',
  NONE: 'is-muted',
};

// F4b source confidence — the official F4 score must disclose when it was built
// from the narrow flagged-alert universe (PROVISIONAL) vs the full options tape.
const SOURCE_CONFIDENCE_LABEL: Record<string, string> = {
  FULL: 'F4 source: FULL',
  PROVISIONAL: 'F4 source: PROVISIONAL',
  NO_DATA: 'F4 source: NO DATA',
};
const SOURCE_CONFIDENCE_TONE: Record<string, string> = {
  FULL: 'is-green',
  PROVISIONAL: 'is-orange',
  NO_DATA: 'is-muted',
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
  // Headline by STATE band, not the legacy BUY/SELL grade (Implementation Audit).
  const stateTone = STATE_TONE[data.f4_state] ?? 'is-yellow';
  const directionTone = DIRECTION_TONE[data.flow_direction] ?? 'is-muted';
  const tierTone = TIER_TONE[data.market_cap_tier] ?? 'is-muted';
  const sourceLabel = SOURCE_LABEL[data.data_source] ?? data.data_source;
  const contribution = Math.round((data.f4_score / 100) * F4_DISPLAY_MAX);
  const chipTone = CHIP_TONE[data.dark_pool_state] ?? 'is-muted';
  const chipLabel = CHIP_LABEL[data.dark_pool_state] ?? data.dark_pool_state;
  const clearanceTone = CLEARANCE_TONE[data.clearance] ?? 'is-yellow';

  return (
    <div className="atlas-f4-content" data-testid="f4-content">
      {/* Score hero — F4b options-flow persistence (headlined by state band) */}
      <div className="atlas-f4-score-hero">
        <div className="atlas-f4-score-ring">
          <span className={cn('atlas-f4-score-number', stateTone)} data-testid="f4-score">
            {data.f4_score}
          </span>
          <span className="atlas-f4-score-denom">/100</span>
        </div>
        <div className="atlas-f4-score-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-f4-grade-pill', stateTone)}
            data-testid="f4-state"
          >
            {data.f4_state}
          </span>
          <span className="atlas-f4-label-sub" data-testid="f4-add-impact">
            {data.f4_add_impact}
          </span>
          <span className="atlas-f4-label-sub" data-testid="f4-live-tape-state">
            live tape: {data.live_tape_state} · {data.persistence_state} (2d)
          </span>
          <span className="atlas-f4-label-sub" data-testid="f4-live-pulse">
            1-day pulse: {data.live_pulse_state ?? 'DATA_GAP'}
            {data.live_pulse_score !== null && data.live_pulse_score !== undefined
              ? ` (${data.live_pulse_score})`
              : ''}
          </span>
          <span className="atlas-f4-label-sub">
            options flow · {contribution}/{F4_DISPLAY_MAX} to F1
          </span>
        </div>
      </div>

      {/* Flow Monitor — the final action gate (the only add authority) */}
      <div className="atlas-f4-signal-row" data-testid="f4-flow-monitor">
        <span className="atlas-f4-label-sub">Flow Monitor</span>
        <span
          className={cn(
            'atlas-frameworks-pill atlas-f4-grade-pill',
            FLOW_MONITOR_TONE[data.flow_monitor_action] ?? 'is-yellow',
          )}
          data-testid="f4-flow-monitor-action"
        >
          {FLOW_MONITOR_LABEL[data.flow_monitor_action] ?? data.flow_monitor_action}
        </span>
      </div>
      {data.flow_monitor_reason && (
        <p className="atlas-f4-state-msg" data-testid="f4-flow-monitor-reason">
          {data.flow_monitor_reason}
        </p>
      )}

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
        <span
          className={cn(
            'atlas-frameworks-pill atlas-f4-tier-pill',
            HEDGE_TONE[data.hedge_structure] ?? 'is-muted',
          )}
          data-testid="f4-hedge-structure"
        >
          {HEDGE_LABEL[data.hedge_structure] ?? data.hedge_structure}
        </span>
      </div>
      {data.clearance_reason && (
        <p className="atlas-f4-state-msg" data-testid="f4-clearance-reason">
          {data.clearance_reason}
        </p>
      )}
      {data.hedge_structure_reason && (
        <p className="atlas-f4-state-msg" data-testid="f4-hedge-structure-reason">
          Hedge context: {data.hedge_structure_reason}
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
        <span
          className={cn(
            'atlas-frameworks-pill atlas-f4-tier-pill',
            SOURCE_CONFIDENCE_TONE[data.f4b_source_confidence] ?? 'is-muted',
          )}
          data-testid="f4-source-confidence"
        >
          {SOURCE_CONFIDENCE_LABEL[data.f4b_source_confidence] ?? data.f4b_source_confidence}
        </span>
      </div>

      {data.f4b_provisional && (
        <p
          className="atlas-f4-state-msg atlas-f4-state-msg--warn"
          data-testid="f4-source-confidence-reason"
        >
          Degraded source: {data.f4b_source_confidence_reason}
        </p>
      )}

      {data.data_gap_reason && (
        <p className="atlas-f4-state-msg atlas-f4-state-msg--warn" data-testid="f4-data-gap-reason">
          {data.data_gap_reason}
        </p>
      )}

      {/* Score bar */}
      <ScoreBar score={data.f4_score} gradeTone={stateTone} />

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

      <F4bDebugCard data={data} />

      <p className="atlas-f4-state-msg" data-testid="f4-firewall-note">
        F4b (scored) = multi-window classified options flow, current session weighted heaviest:
        bullish (call-buy + put-sell) vs bearish (put-buy + call-sell), moneyness/expiry-weighted →
        bullish share
        {data.bullish_share !== null && data.bullish_share !== undefined
          ? ` ${Math.round(data.bullish_share * 100)}%`
          : ''}
        . F4a equity / dark-pool is NOT scored — it confirms action via the Flow Monitor (shown as
        the dark-pool chip / clearance overlay below).
      </p>

      {data.dark_pool_state_reason && (
        <p className="atlas-f4-state-msg" data-testid="f4-dark-pool-state-reason">
          Stock tape (overlay): {data.dark_pool_state_reason}
        </p>
      )}

      <p className="atlas-f4-state-msg" data-testid="f4a-confidence">
        F4a dark-pool confidence: {data.dark_pool_confidence}
      </p>
      {data.dark_pool_confidence.toLowerCase().includes('low') && (
        <span
          className="atlas-frameworks-pill atlas-f4-tier-pill is-orange"
          data-testid="f4a-low-confidence-badge"
        >
          LOW CONFIDENCE
        </span>
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
    <SubCardShell
      label="Dark Pool · Equity Accum (F4a)"
      testIdSlug="dark-pool"
      score={score}
      scored={false}
    >
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
    <SubCardShell
      label="Options Flow (F4b · scored)"
      testIdSlug="options"
      score={score}
      scored={true}
    >
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

function F4bDebugCard({ data }: { data: OptionsFlowResponse }) {
  const hasValue = (value: number | null | undefined): boolean =>
    value !== null && value !== undefined;
  const hasDebugFields =
    hasValue(data.raw_bull_premium_usd) ||
    hasValue(data.raw_bear_premium_usd) ||
    hasValue(data.raw_bullish_share) ||
    hasValue(data.raw_largest_bullish_print_usd) ||
    hasValue(data.raw_largest_call_ask_print_usd) ||
    hasValue(data.adjusted_bull_premium_usd) ||
    hasValue(data.adjusted_bear_premium_usd) ||
    hasValue(data.adjusted_bullish_share) ||
    hasValue(data.adjusted_largest_bullish_print_usd) ||
    Boolean(
      data.declassified_premium_by_reason &&
      Object.keys(data.declassified_premium_by_reason).length > 0,
    );

  if (!hasDebugFields) {
    return null;
  }

  const declassifiedEntries = Object.entries(data.declassified_premium_by_reason ?? {}).sort(
    ([left], [right]) => left.localeCompare(right),
  );

  return (
    <article className="atlas-f4-indicator" data-testid="f4b-debug">
      <header className="atlas-f4-indicator-header">
        <span className="atlas-f4-indicator-label">F4b Debug Bridge</span>
        <span className="atlas-frameworks-pill atlas-f4-tier-pill is-muted">raw → adjusted</span>
      </header>
      <div className="atlas-f4-indicator-body">
        <dl className="atlas-f4-dl">
          <DebugRow label="Raw Bull Premium" value={formatNullableUsd(data.raw_bull_premium_usd)} />
          <DebugRow label="Raw Bear Premium" value={formatNullableUsd(data.raw_bear_premium_usd)} />
          <DebugRow label="Raw Bull Share" value={formatNullablePercent(data.raw_bullish_share)} />
          <DebugRow
            label="Raw Largest Bullish Print"
            value={formatNullableUsd(data.raw_largest_bullish_print_usd)}
          />
          <DebugRow
            label="Raw Largest Call-Ask Print"
            value={formatNullableUsd(data.raw_largest_call_ask_print_usd)}
          />
          <DebugRow
            label="Adjusted Bull Premium"
            value={formatNullableUsd(data.adjusted_bull_premium_usd)}
          />
          <DebugRow
            label="Adjusted Bear Premium"
            value={formatNullableUsd(data.adjusted_bear_premium_usd)}
          />
          <DebugRow
            label="Adjusted Bull Share"
            value={formatNullablePercent(data.adjusted_bullish_share)}
          />
          <DebugRow
            label="Adjusted Largest Bullish Print"
            value={formatNullableUsd(data.adjusted_largest_bullish_print_usd)}
          />
          <DebugRow label="Final F4b Score" value={String(data.f4_score)} />
          <DebugRow label="Final score input" value={data.f4b_score_input_source ?? '—'} />
          <DebugRow label="Universe source" value={data.f4b_universe_source ?? '—'} />
          <DebugRow label="Source confidence" value={data.f4b_source_confidence ?? '—'} />
          {data.f4b_full_tape_score !== null && data.f4b_full_tape_score !== undefined && (
            <DebugRow
              label="Full-tape candidate (FULL coverage)"
              value={`${data.f4b_full_tape_score} · ${data.f4b_full_tape_source} · ${
                data.f4b_full_tape_bullish_share !== null &&
                data.f4b_full_tape_bullish_share !== undefined
                  ? `${Math.round(data.f4b_full_tape_bullish_share * 100)}% bull share`
                  : '—'
              }`}
            />
          )}
          <DebugRow
            label="Universe alerts"
            value={
              data.f4b_universe_total_alerts !== undefined
                ? `${data.f4b_universe_total_alerts} total · ${data.f4b_universe_directional_alerts ?? 0} directional · ${data.f4b_universe_excluded_alerts ?? 0} excluded`
                : '—'
            }
          />
          <DebugRow
            label="Raw Buckets"
            value={
              hasValue(data.raw_call_ask_premium_usd) ||
              hasValue(data.raw_call_bid_premium_usd) ||
              hasValue(data.raw_put_ask_premium_usd) ||
              hasValue(data.raw_put_bid_premium_usd)
                ? `call ask ${formatNullableUsd(data.raw_call_ask_premium_usd)} · call bid ${formatNullableUsd(data.raw_call_bid_premium_usd)} · put ask ${formatNullableUsd(data.raw_put_ask_premium_usd)} · put bid ${formatNullableUsd(data.raw_put_bid_premium_usd)}`
                : '—'
            }
          />
          {declassifiedEntries.map(([reason, value]) => (
            <DebugRow key={reason} label={reason} value={formatMillions(value)} />
          ))}
        </dl>
      </div>
    </article>
  );
}

function DebugRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="atlas-f4-dl-row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
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

function formatNullableUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return formatMillions(value);
}

function formatNullablePercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(1)}%`;
}

function netFlowTone(value: number | null): string {
  if (value === null || value === 0) return 'is-muted';
  return value > 0 ? 'is-green' : 'is-red';
}
