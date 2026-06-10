'use client';

import { cn } from '@/lib/utils';
import { useAnalyst } from '@/lib/hooks/use-analyst';
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

/** Map consensus label string to CSS tone class name. */
const GRADE_TONE: Record<string, string> = {
  'STRONG BUY': 'is-green',
  BUY: 'is-cyan',
  NEUTRAL: 'is-yellow',
  WEAK: 'is-orange',
  AVOID: 'is-red',
  HOLD: 'is-yellow',
  SELL: 'is-red',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

type F3AnalystPanelProps = {
  /** Active ticker symbol chosen by the shared selector in FrameworksPanelsSection. */
  ticker: string;
};

/**
 * F3 Analyst Conviction panel — v7.3.4 base-score + modifier approach.
 *
 * Five sub-indicators:
 *   Consensus Rating (base score) | Analyst Coverage (modifier)
 *   PT Direction (modifier) | Recent Upgrades (modifier)
 *   PT Upside (adjustment)
 *
 * Data source: Benzinga (consensus + calendar ratings) + Polygon (price).
 */
export function F3AnalystPanel({ ticker }: F3AnalystPanelProps) {
  const { data, isFetching, isError, error } = useAnalyst(ticker);

  return (
    <section className="atlas-frameworks-panel atlas-f3-panel" data-testid="f3-analyst-panel">
      <header className="atlas-frameworks-panel-header atlas-f3-panel-header">
        <h2 className="atlas-frameworks-panel-title">F3 Analyst Conviction</h2>
      </header>

      <div className="atlas-f3-panel-body">
        {isFetching && <LoadingState />}
        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Failed to load analyst data.'}
          />
        )}
        {!isFetching && !isError && data && data.f3_score === null && (
          <DegradedBanner reason="No analyst coverage found on Benzinga or Alpha Vantage for this ticker — consensus rating, price target, and revision data are unavailable." />
        )}
        {!isFetching && !isError && data && <AnalystContent data={data} />}
        {!isFetching && !isError && !data && ticker && <EmptyState ticker={ticker} />}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// State components
// ---------------------------------------------------------------------------

function DegradedBanner({ reason }: { reason: string }) {
  return (
    <div className="atlas-f3-degraded-banner" data-testid="f3-degraded">
      <span className="atlas-f3-degraded-icon">⚠</span>
      <span className="atlas-f3-degraded-msg">{reason}</span>
    </div>
  );
}

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
// Main content
// ---------------------------------------------------------------------------

function AnalystContent({ data }: { data: AnalystResponse }) {
  // Use consensus label (e.g. "BUY") for header display — NOT f3_grade which is
  // derived from the numeric score alone and can disagree with the consensus label.
  const consensusLabel = data.consensus_rating.label;
  const gradeTone = GRADE_TONE[consensusLabel] ?? 'is-yellow';

  return (
    <div className="atlas-f3-content" data-testid="f3-content">
      {/* F3 Score hero */}
      <div className="atlas-f3-score-hero">
        <div className="atlas-f3-score-ring">
          {data.f3_score !== null ? (
            <span className={cn('atlas-f3-score-number', gradeTone)} data-testid="f3-score">
              {data.f3_score}
            </span>
          ) : (
            <span className="atlas-f3-score-number is-muted" data-testid="f3-score">N/A</span>
          )}
          <span className="atlas-f3-score-denom">/100</span>
        </div>
        <div className="atlas-f3-score-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-f3-grade-pill', gradeTone)}
            data-testid="f3-grade"
          >
            {consensusLabel}
          </span>
          {data.override_applied && (
            <span className="atlas-f3-override-chip" data-testid="f3-override-chip">
              HIGH CONSENSUS OVERRIDE
            </span>
          )}
          <span className="atlas-f3-label-sub">Analyst Conviction</span>
        </div>
      </div>

      {/* Score bar */}
      <ScoreBar score={data.f3_score} gradeTone={gradeTone} />

      {/* Five indicator cards */}
      <div className="atlas-f3-indicators">
        <ConsensusRatingCard consensus={data.consensus_rating} />
        <AnalystCoverageCard coverage={data.analyst_coverage} />
        <PtDirectionCard ptDirection={data.pt_direction} />
        <RecentUpgradesCard recent={data.recent_upgrades} />
        <PtUpsideCard pt={data.pt_upside} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score bar
// ---------------------------------------------------------------------------

function ScoreBar({ score, gradeTone }: { score: number | null; gradeTone: string }) {
  const filled = score !== null ? Math.round((score / 100) * SCORE_BAR_SEGMENTS) : 0;

  return (
    <div
      className="atlas-f3-score-bar"
      role="progressbar"
      aria-valuenow={score ?? undefined}
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
  modifier?: number | null;
  children: React.ReactNode;
};

function IndicatorCard({ label, modifier, children }: IndicatorCardProps) {
  const testId = `f3-indicator-${label.toLowerCase().replace(/[\s/]+/g, '-')}`;
  return (
    <article className="atlas-f3-indicator" data-testid={testId}>
      <header className="atlas-f3-indicator-header">
        <span className="atlas-f3-indicator-label">{label}</span>
        {modifier !== undefined && modifier !== null && (
          <span className={cn('atlas-f3-indicator-modifier', modifier >= 0 ? 'is-cyan' : 'is-red')}>
            {modifier >= 0 ? `+${modifier}` : modifier}
          </span>
        )}
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
    <IndicatorCard
      label="Consensus Rating"
      modifier={consensus.base_score}
    >
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Consensus</dt>
          <dd className={consensusTone(consensus.label)} data-testid="f3-consensus-label">
            {consensus.label === 'NO DATA' ? 'No data found' : consensus.label}
          </dd>
        </div>
        {consensus.buy_pct !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Buy %</dt>
            <dd>{consensus.buy_pct.toFixed(1)}%</dd>
          </div>
        )}
        <div className="atlas-f3-dl-row">
          <dt>SB / B / H / S / SS</dt>
          <dd>
            {consensus.strong_buy_count} / {consensus.buy_count} / {consensus.hold_count} /{' '}
            {consensus.sell_count} / {consensus.strong_sell_count}
          </dd>
        </div>
      </dl>
      {consensus.total_analysts > 0 && (
        <div className="atlas-f3-consensus-bar" aria-hidden="true">
          {consensus.strong_buy_count + consensus.buy_count > 0 && (
            <span
              className="atlas-f3-consensus-bar-buy"
              style={{
                width: `${((consensus.strong_buy_count + consensus.buy_count) / consensus.total_analysts) * 100}%`,
              }}
            />
          )}
          {consensus.hold_count > 0 && (
            <span
              className="atlas-f3-consensus-bar-hold"
              style={{ width: `${(consensus.hold_count / consensus.total_analysts) * 100}%` }}
            />
          )}
          {consensus.sell_count + consensus.strong_sell_count > 0 && (
            <span
              className="atlas-f3-consensus-bar-sell"
              style={{
                width: `${((consensus.sell_count + consensus.strong_sell_count) / consensus.total_analysts) * 100}%`,
              }}
            />
          )}
        </div>
      )}
    </IndicatorCard>
  );
}

function AnalystCoverageCard({ coverage }: { coverage: AnalystCoverageIndicator }) {
  return (
    <IndicatorCard label="Analyst Coverage" modifier={coverage.modifier}>
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Analysts</dt>
          <dd className={coverageTone(coverage.num_analysts)}>
            {coverage.num_analysts > 0 ? coverage.num_analysts : 'No data found'}
          </dd>
        </div>
        {coverage.num_analysts > 0 && (
          <div className="atlas-f3-dl-row">
            <dt>Reliability</dt>
            <dd>{coverageLabel(coverage.num_analysts)}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function PtDirectionCard({ ptDirection }: { ptDirection: PtDirectionIndicator }) {
  const isNoData = ptDirection.direction_label === 'NO_DATA';
  return (
    <IndicatorCard label="PT Direction" modifier={ptDirection.modifier}>
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Signal</dt>
          <dd
            className={isNoData ? 'is-muted' : ptDirectionTone(ptDirection.direction_label)}
            data-testid="f3-pt-direction-label"
          >
            {isNoData ? 'No data found' : ptDirection.direction_label}
          </dd>
        </div>
        {!isNoData && (
          <>
            <div className="atlas-f3-dl-row">
              <dt>Raises (30d)</dt>
              <dd
                className={
                  ptDirection.raises_30d >= 2
                    ? 'is-green'
                    : ptDirection.raises_30d === 1
                      ? 'is-cyan'
                      : ''
                }
              >
                {ptDirection.raises_30d}
              </dd>
            </div>
            <div className="atlas-f3-dl-row">
              <dt>Lowers (30d)</dt>
              <dd className={ptDirection.lowers_30d > 0 ? 'is-red' : ''}>
                {ptDirection.lowers_30d}
              </dd>
            </div>
          </>
        )}
      </dl>
    </IndicatorCard>
  );
}

function RecentUpgradesCard({ recent }: { recent: RecentUpgradesIndicator }) {
  return (
    <IndicatorCard label="Recent Upgrades" modifier={recent.modifier}>
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          <dt>Net (30d)</dt>
          <dd className={recent.net_upgrades_30d > 0 ? 'is-green' : recent.net_upgrades_30d < 0 ? 'is-red' : ''}>
            {recent.net_upgrades_30d > 0 ? `+${recent.net_upgrades_30d}` : recent.net_upgrades_30d}
          </dd>
        </div>
        <div className="atlas-f3-dl-row">
          <dt>Upgrades / Downgrades</dt>
          <dd>
            {recent.upgrades_30d} / {recent.downgrades_30d}
          </dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function PtUpsideCard({ pt }: { pt: PtUpsideIndicator }) {
  // Derive CSS class from the band token or band string — never from the sign
  // of upside_pct. A negative upside (price above target) in the neutral zone
  // must show grey, not red.
  const upside_cls = upsideBandClass(pt.price_vs_target_band, pt.upside_color);
  return (
    <IndicatorCard label="PT Upside" modifier={pt.adjustment}>
      <dl className="atlas-f3-dl">
        <div className="atlas-f3-dl-row">
          {/* Upside is computed vs the Street-high PT, so label it as such — it
              must reconcile with the "Street-high PT" row below, NOT with the
              consensus PT (the stock can sit above consensus yet below the high). */}
          <dt>Upside vs high PT</dt>
          <dd className={upside_cls}>
            {pt.upside_pct !== null ? formatPct(pt.upside_pct) : 'No data found'}
          </dd>
        </div>
        {pt.price_vs_target_band != null && (
          <div className="atlas-f3-dl-row">
            <dt>Band</dt>
            <dd className={cn('atlas-f3-pt-band', upside_cls)}>{pt.price_vs_target_band}</dd>
          </div>
        )}
        {pt.current_price !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Current Price</dt>
            <dd>{formatPrice(pt.current_price)}</dd>
          </div>
        )}
        {pt.highest_pt != null && (
          <div className="atlas-f3-dl-row">
            <dt>Street-high PT</dt>
            <dd>{formatPrice(pt.highest_pt)}</dd>
          </div>
        )}
        {pt.consensus_pt !== null && (
          <div className="atlas-f3-dl-row">
            <dt>Consensus PT</dt>
            <dd className={consensusToneCls(pt.current_price, pt.consensus_pt)}>
              {formatPrice(pt.consensus_pt)}
              {consensusUpside(pt.current_price, pt.consensus_pt)}
            </dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

// ---------------------------------------------------------------------------
// Formatting and tone helpers
// ---------------------------------------------------------------------------

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function formatPrice(value: number): string {
  return `$${value.toFixed(2)}`;
}

/** Consensus-based upside annotation, e.g. " (−3.4%)". Empty when data is missing. */
function consensusUpside(price: number | null, consensusPt: number | null): string {
  if (price == null || consensusPt == null || price <= 0) return '';
  return ` (${formatPct(((consensusPt - price) / price) * 100)})`;
}

/** Amber when the stock trades ABOVE consensus PT (a caution), neutral otherwise. */
function consensusToneCls(price: number | null, consensusPt: number | null): string {
  if (price == null || consensusPt == null) return '';
  return price > consensusPt ? 'atlas-f3-upside-amber' : 'atlas-f3-upside-neutral';
}

function consensusTone(label: string): string {
  if (label === 'STRONG BUY') return 'is-green';
  if (label === 'BUY') return 'is-cyan';
  if (label === 'HOLD') return 'is-yellow';
  if (label === 'SELL') return 'is-red';
  return '';
}

/**
 * Map band token or band display string to a CSS class.
 *
 * Priority 1 — `upside_color` token from the API (e.g. 'NEUTRAL', 'GREEN').
 * Priority 2 — `price_vs_target_band` display string from the API
 *              (e.g. 'At target — neutral (0)').
 *
 * NEVER derives class from the sign of upside_pct.
 * A negative upside inside the neutral band must return 'atlas-f3-upside-neutral'
 * (grey), not any red class.
 *
 * CSS classes are defined in frameworks.css under the
 * '/* Upside band colour classes *\/' block.
 */
function upsideBandClass(
  band: string | null | undefined,
  upsideColor?: string | null,
): string {
  // Priority 1: explicit upside_color token from the API
  if (upsideColor === 'GREEN') return 'atlas-f3-upside-green';
  if (upsideColor === 'LIGHT_GREEN') return 'atlas-f3-upside-light-green';
  if (upsideColor === 'NEUTRAL') return 'atlas-f3-upside-neutral';
  if (upsideColor === 'AMBER') return 'atlas-f3-upside-amber';
  if (upsideColor === 'RED') return 'atlas-f3-upside-red';
  // Priority 2: derive from the band display string
  if (!band) return 'atlas-f3-upside-neutral';
  if (band.startsWith('20%+ below')) return 'atlas-f3-upside-green';
  if (band.startsWith('10-20% below')) return 'atlas-f3-upside-light-green';
  if (band.startsWith('At target')) return 'atlas-f3-upside-neutral';
  if (band.startsWith('10-20% above')) return 'atlas-f3-upside-amber';
  if (band.startsWith('20%+ above')) return 'atlas-f3-upside-red';
  return 'atlas-f3-upside-neutral';
}

function ptDirectionTone(label: string): string {
  if (label === 'MULTIPLE_RAISES') return 'is-green';
  if (label === 'SINGLE_RAISE') return 'is-cyan';
  if (label === 'NO_CHANGE') return 'is-yellow';
  return 'is-red';
}

function coverageTone(count: number): string {
  if (count > 20) return 'is-green';
  if (count >= 10) return 'is-cyan';
  if (count >= 5) return 'is-yellow';
  return 'is-orange';
}

function coverageLabel(count: number): string {
  if (count > 20) return 'High';
  if (count >= 10) return 'Good';
  if (count >= 5) return 'Moderate';
  return 'Thin (<5)';
}
