'use client';

import { cn } from '@/lib/utils';
import { useEarnings } from '@/lib/hooks/use-earnings';
import type { EarningsResponse } from '@/lib/schemas/earnings';

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

const FWD_VIS_LABEL: Record<string, string> = {
  SPECIFIC_RAISED: 'Guidance Raised',
  SPECIFIC_MAINTAINED: 'Guidance Maintained',
  DIRECTIONAL: 'Directional Only',
  VAGUE_NONE: 'Vague / None',
  WITHDRAWN_REDUCED: 'Withdrawn / Reduced',
};

const FWD_VIS_TONE: Record<string, string> = {
  SPECIFIC_RAISED: 'is-green',
  SPECIFIC_MAINTAINED: 'is-cyan',
  DIRECTIONAL: 'is-yellow',
  VAGUE_NONE: 'is-muted',
  WITHDRAWN_REDUCED: 'is-red',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

type F2EarningsPanelProps = {
  ticker: string;
};

export function F2EarningsPanel({ ticker }: F2EarningsPanelProps) {
  const { data, isFetching, isError, error } = useEarnings(ticker);

  return (
    <section className="atlas-frameworks-panel atlas-f2-panel" data-testid="f2-earnings-panel">
      <header className="atlas-frameworks-panel-header atlas-f2-panel-header">
        <h2 className="atlas-frameworks-panel-title">F2 Earnings Quality</h2>
      </header>

      <div className="atlas-f2-panel-body">
        {isFetching && <LoadingState />}
        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Failed to load earnings data.'}
          />
        )}
        {!isFetching && !isError && data && data.data_available === false && (
          <DegradedBanner reason="Alpha Vantage rate limit reached — income statement and EPS data unavailable. Earnings score is a neutral fallback. Try again in ~1 minute." />
        )}
        {!isFetching && !isError && data && <EarningsContent data={data} />}
        {!isFetching && !isError && !data && ticker && <EmptyState ticker={ticker} />}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// State components
// ---------------------------------------------------------------------------

function LoadingState() {
  return <p className="atlas-f2-state-msg" data-testid="f2-loading">Analysing earnings quality…</p>;
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

function DegradedBanner({ reason }: { reason: string }) {
  return (
    <div className="atlas-f2-degraded-banner" data-testid="f2-degraded">
      <span className="atlas-f2-degraded-icon">⚠</span>
      <span className="atlas-f2-degraded-msg">{reason}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main content
// ---------------------------------------------------------------------------

function qualityLabel(score: number): { label: string; tone: string } {
  if (score >= 85) return { label: 'STRONG', tone: 'is-green' };
  if (score >= 70) return { label: 'GOOD', tone: 'is-cyan' };
  if (score >= 55) return { label: 'MODERATE', tone: 'is-yellow' };
  return { label: 'WEAK', tone: 'is-red' };
}

function EarningsContent({ data }: { data: EarningsResponse }) {
  const quality = qualityLabel(data.f2_score);

  return (
    <div className="atlas-f2-content" data-testid="f2-content">
      {/* Score hero */}
      <div className="atlas-f2-score-hero">
        <div className="atlas-f2-score-ring">
          <span className={cn('atlas-f2-score-number', quality.tone)} data-testid="f2-score">
            {data.f2_score}
          </span>
          <span className="atlas-f2-score-denom">/100</span>
        </div>
        <div className="atlas-f2-score-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-f2-grade-pill', quality.tone)}
            data-testid="f2-grade"
          >
            {quality.label}
          </span>
          <span className="atlas-f2-label-sub">Earnings Quality</span>
        </div>
      </div>

      {/* Flag badges — column layout prevents badge text from merging */}
      <div className="atlas-f2-flags" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '6px' }}>
        {data.pre_profit_status && (
          <span className="atlas-f2-flag is-amber" data-testid="f2-flag-pre-profit">
            Pre-Profitability
          </span>
        )}
        {data.data_gap_applied && (
          <span className="atlas-f2-flag is-amber" data-testid="f2-flag-data-gap">
            DATA GAP — Guidance
          </span>
        )}
        {data.exit_flag && (
          <span className="atlas-f2-flag is-red" data-testid="f2-flag-exit">
            EXIT SIGNAL
          </span>
        )}
        {data.guidance_concern && (
          <span className="atlas-f2-flag is-red" data-testid="f2-flag-guidance-concern">
            Guidance Concern
          </span>
        )}
        {data.limited_history && (
          <span className="atlas-f2-flag is-muted" data-testid="f2-flag-limited-history">
            Limited History
          </span>
        )}
      </div>

      {/* Sub-factor grid */}
      <div className="atlas-f2-indicators">
        <Sf1RevenueGrowthCard data={data} />
        <Sf2GrossMarginCard data={data} />
        <Sf3EpsBeatsCard data={data} />
        <Sf4GuidanceReliabilityCard data={data} />
        <Sf5ForwardVisibilityCard data={data} />
      </div>

      {/* F2 composite — two separate labeled rows */}
      <div className="atlas-f2-composite" data-testid="f2-composite">
        <div className="atlas-f2-composite-row">
          <span className="atlas-f2-composite-label">F2 Raw Score</span>
          <span className="atlas-f2-composite-raw" data-testid="f2-raw">{data.f2_raw.toFixed(1)}</span>
        </div>
        <div className="atlas-f2-composite-row">
          <span className="atlas-f2-composite-label">F2 Contribution (×0.25)</span>
          <span className="atlas-f2-composite-contrib" data-testid="f2-contribution">
            {data.f2_contribution.toFixed(1)}
          </span>
        </div>
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
    <div className="atlas-f2-score-bar" role="progressbar" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100}>
      {Array.from({ length: SCORE_BAR_SEGMENTS }, (_, i) => (
        <span key={i} className={cn('atlas-f2-score-bar-seg', i < filled ? gradeTone : 'is-empty')} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-factor cards
// ---------------------------------------------------------------------------

type SubFactorCardProps = {
  id: string;
  label: string;
  score: number | null;
  weight: string;
  children: React.ReactNode;
};

function SubFactorCard({ id, label, score, weight, children }: SubFactorCardProps) {
  const tone = score === null ? 'is-muted' : scoreTone(score);
  return (
    <article className="atlas-f2-indicator" data-testid={`f2-indicator-${id}`}>
      <header className="atlas-f2-indicator-header">
        <span className="atlas-f2-indicator-label">{label}</span>
        <span className="atlas-f2-indicator-weight">{weight}</span>
        <span className={cn('atlas-f2-indicator-score', tone)}>
          {score !== null ? score.toFixed(0) : 'N/A'}
          <span className="atlas-f2-indicator-max">/100</span>
        </span>
      </header>
      {score !== null && <ScoreBar score={score} gradeTone={tone} />}
      <div className="atlas-f2-indicator-body">{children}</div>
    </article>
  );
}

function Sf1RevenueGrowthCard({ data }: { data: EarningsResponse }) {
  const pct = data.sf1_revenue_growth_pct;
  return (
    <SubFactorCard id="revenue-growth" label="Revenue Growth" score={data.sf1_score} weight="30%">
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>YoY Growth</dt>
          <dd className={pct !== null ? growthTone(pct) : ''}>
            {pct !== null ? formatPct(pct) : '—'}
          </dd>
        </div>
      </dl>
    </SubFactorCard>
  );
}

function Sf2GrossMarginCard({ data }: { data: EarningsResponse }) {
  const bps = data.sf2_gross_margin_trend_bps;
  return (
    <SubFactorCard id="gross-margin-trend" label="Gross Margin Trend" score={data.sf2_score} weight="20%">
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>YoY Change</dt>
          <dd className={bps !== null ? bpsTone(bps) : ''}>
            {bps !== null ? `${bps >= 0 ? '+' : ''}${bps.toFixed(0)} bps` : '—'}
          </dd>
        </div>
      </dl>
    </SubFactorCard>
  );
}

function Sf3EpsBeatsCard({ data }: { data: EarningsResponse }) {
  if (data.sf3_excluded) {
    return (
      <SubFactorCard id="eps-consistency" label="EPS Beat Consistency" score={null} weight="20%">
        <p className="atlas-f2-excluded-note" data-testid="f2-sf3-excluded">
          Excluded — pre-profitability
        </p>
      </SubFactorCard>
    );
  }

  const beats = data.sf3_eps_beats;
  const avail = data.sf3_quarters_available;
  return (
    <SubFactorCard id="eps-consistency" label="EPS Beat Consistency" score={data.sf3_score} weight="20%">
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>Beats (Last {avail}Q)</dt>
          <dd className={beats !== null ? beatsTone(beats, avail) : ''}>
            {beats !== null ? `${beats}/${avail}` : '—'}
          </dd>
        </div>
      </dl>
      {data.ipo_limited_history && (
        <p className="atlas-f2-note is-muted" data-testid="f2-sf3-limited-history">
          Limited history — scored proportionally
        </p>
      )}
    </SubFactorCard>
  );
}

function Sf4GuidanceReliabilityCard({ data }: { data: EarningsResponse }) {
  return (
    <SubFactorCard id="guidance-reliability" label="Guidance Reliability" score={data.sf4_score} weight="15%">
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>Delivered (4Q)</dt>
          <dd>
            {data.sf4_data_gap ? (
              <span className="is-muted" data-testid="f2-sf4-data-gap">DATA GAP (default 10)</span>
            ) : (
              <span>{data.sf4_guidance_delivered ?? '—'}/4</span>
            )}
          </dd>
        </div>
      </dl>
    </SubFactorCard>
  );
}

function Sf5ForwardVisibilityCard({ data }: { data: EarningsResponse }) {
  const label = FWD_VIS_LABEL[data.sf5_forward_visibility_label] ?? data.sf5_forward_visibility_label;
  const tone = FWD_VIS_TONE[data.sf5_forward_visibility_label] ?? 'is-muted';
  return (
    <SubFactorCard id="forward-visibility" label="Forward Visibility" score={data.sf5_score} weight="15%">
      <dl className="atlas-f2-dl">
        <div className="atlas-f2-dl-row">
          <dt>Signal</dt>
          <dd className={tone}>{label}</dd>
        </div>
      </dl>
    </SubFactorCard>
  );
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function scoreTone(score: number): string {
  if (score >= 80) return 'is-green';
  if (score >= 65) return 'is-cyan';
  if (score >= 40) return 'is-yellow';
  if (score >= 20) return 'is-orange';
  return 'is-red';
}

function growthTone(pct: number): string {
  if (pct >= 40) return 'is-green';
  if (pct >= 15) return 'is-cyan';
  if (pct >= 0) return 'is-yellow';
  return 'is-red';
}

function bpsTone(bps: number): string {
  if (bps > 100) return 'is-green';
  if (bps >= -50) return 'is-yellow';
  return 'is-red';
}

function beatsTone(beats: number, avail: number): string {
  if (avail === 0) return '';
  const rate = beats / avail;
  if (rate >= 1.0) return 'is-green';
  if (rate >= 0.75) return 'is-cyan';
  if (rate >= 0.5) return 'is-yellow';
  return 'is-red';
}

