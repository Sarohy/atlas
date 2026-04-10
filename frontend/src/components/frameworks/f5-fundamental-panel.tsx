'use client';

import { cn } from '@/lib/utils';
import { useFundamental } from '@/lib/hooks/use-fundamental';
import type {
  AltmanZScoreIndicator,
  DebtEquityIndicator,
  FreeCashFlowIndicator,
  FundamentalResponse,
  InsiderActivityIndicator,
  InstitutionalOwnershipIndicator,
} from '@/lib/schemas/fundamental';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

const SCORE_BAR_SEGMENTS = 10;

const GRADE_TONE: Record<string, string> = {
  STRONG: 'is-green',
  GOOD: 'is-cyan',
  NEUTRAL: 'is-yellow',
  WEAK: 'is-orange',
  DISTRESSED: 'is-red',
};

const ZONE_TONE: Record<string, string> = {
  SAFE: 'is-green',
  GREY: 'is-orange',
  DISTRESSED: 'is-red',
  UNKNOWN: 'is-muted',
};

const ACTIVITY_TONE: Record<string, string> = {
  NET_BUYING: 'is-green',
  NO_ACTIVITY: 'is-muted',
  SMALL_SALE: 'is-yellow',
  MULTIPLE_SALES: 'is-orange',
  CEO_MEGA_SALE: 'is-red',
};

const FCF_TONE: Record<string, string> = {
  POSITIVE_GROWING: 'is-green',
  POSITIVE_FLAT: 'is-cyan',
  POSITIVE_DECLINING: 'is-yellow',
  NEGATIVE_IMPROVING: 'is-orange',
  NEGATIVE_WORSENING: 'is-red',
  UNKNOWN: 'is-muted',
};

const INST_TONE: Record<string, string> = {
  NET_BUYING: 'is-green',
  FLAT: 'is-cyan',
  SMALL_SELLING: 'is-yellow',
  LARGE_SELLING: 'is-red',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

type F5FundamentalPanelProps = {
  /** Active ticker symbol chosen by the shared selector in FrameworksPanelsSection. */
  ticker: string;
};

/**
 * F5 Fundamental Quality panel — receives the active ticker from the shared
 * selector and shows insider activity, Altman Z-Score, free cash flow,
 * debt/equity ratio, and institutional ownership plus the weighted F5 score.
 *
 * Five sub-indicators per Factor_Mapping_Guide:
 *   Insider Activity (30%) | Altman Z-Score (25%) | Free Cash Flow (20%)
 *   Debt/Equity (15%) | Institutional Ownership (10%)
 *
 * Data sources: sec-api.io (Form 4) + Alpha Vantage (balance sheet, income, cash flow, overview).
 * Caps: C-suite sell >$1M → 72 | CEO/CFO >$10M → 65 | Altman grey zone → 75.
 * Hard block: Altman Z < 1.8 → new capital blocked.
 */
export function F5FundamentalPanel({ ticker }: F5FundamentalPanelProps) {
  const { data, isFetching, isError, error } = useFundamental(ticker);

  return (
    <section className="atlas-frameworks-panel atlas-f5-panel" data-testid="f5-fundamental-panel">
      <header className="atlas-frameworks-panel-header atlas-f5-panel-header">
        <h2 className="atlas-frameworks-panel-title">F5 Fundamental Quality</h2>
      </header>

      <div className="atlas-f5-panel-body">
        {isFetching && <LoadingState />}
        {isError && (
          <ErrorState
            message={error instanceof Error ? error.message : 'Failed to load fundamental data.'}
          />
        )}
        {!isFetching && !isError && data && <FundamentalContent data={data} />}
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
    <p className="atlas-f5-state-msg" data-testid="f5-loading">
      Analysing fundamentals…
    </p>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="atlas-f5-state-msg atlas-f5-state-msg--error" data-testid="f5-error">
      {message}
    </p>
  );
}

function EmptyState({ ticker }: { ticker: string }) {
  return (
    <p className="atlas-f5-state-msg" data-testid="f5-empty">
      No fundamental data available for {ticker}.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main content
// ---------------------------------------------------------------------------

function FundamentalContent({ data }: { data: FundamentalResponse }) {
  const gradeTone = GRADE_TONE[data.f5_grade] ?? 'is-yellow';

  return (
    <div className="atlas-f5-content" data-testid="f5-content">
      {/* Score hero */}
      <div className="atlas-f5-score-hero">
        <div className="atlas-f5-score-ring">
          <span className={cn('atlas-f5-score-number', gradeTone)} data-testid="f5-score">
            {data.f5_score}
          </span>
          <span className="atlas-f5-score-denom">/100</span>
        </div>
        <div className="atlas-f5-score-meta">
          <span
            className={cn('atlas-frameworks-pill atlas-f5-grade-pill', gradeTone)}
            data-testid="f5-grade"
          >
            {data.f5_grade}
          </span>
          <span className="atlas-f5-label-sub">Fundamental Quality</span>
        </div>
      </div>

      {/* Flags row */}
      <FlagsRow data={data} />

      {/* Score bar */}
      <ScoreBar score={data.f5_score} gradeTone={gradeTone} />

      {/* Five weighted indicator cards */}
      <div className="atlas-f5-indicators">
        <InsiderActivityCard insider={data.insider_activity} />
        <AltmanZCard altman={data.altman_z} />
        <FreeCashFlowCard fcf={data.free_cash_flow} />
        <DebtEquityCard de={data.debt_equity} />
        <InstitutionalOwnershipCard inst={data.institutional_ownership} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Flags row
// ---------------------------------------------------------------------------

function FlagsRow({ data }: { data: FundamentalResponse }) {
  const hasFlags = data.f5_blocked || data.insider_cap !== null || data.altman_cap !== null;
  if (!hasFlags) return null;

  return (
    <div className="atlas-f5-flags-row">
      {data.f5_blocked && (
        <span
          className="atlas-frameworks-pill atlas-f5-flag-pill is-red"
          data-testid="f5-distress-block"
        >
          DISTRESS BLOCK — NEW CAPITAL BLOCKED
        </span>
      )}
      {!data.f5_blocked && data.active_cap !== null && (
        <span
          className="atlas-frameworks-pill atlas-f5-flag-pill is-orange"
          data-testid="f5-active-cap"
        >
          CAPPED AT {data.active_cap}
          {data.insider_cap !== null && data.altman_cap !== null
            ? ` (insider + grey zone)`
            : data.insider_cap !== null
              ? ` (insider selling)`
              : ` (grey zone)`}
        </span>
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
      className="atlas-f5-score-bar"
      role="progressbar"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {Array.from({ length: SCORE_BAR_SEGMENTS }, (_, i) => (
        <span
          key={i}
          className={cn('atlas-f5-score-bar-seg', i < filled ? gradeTone : 'is-empty')}
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
  weight: number;
  children: React.ReactNode;
};

function IndicatorCard({ label, score, children }: IndicatorCardProps) {
  return (
    <article
      className="atlas-f5-indicator"
      data-testid={`f5-indicator-${label.toLowerCase().replace(/[\s/]+/g, '-')}`}
    >
      <header className="atlas-f5-indicator-header">
        <span className="atlas-f5-indicator-label">{label}</span>
        <span className="atlas-f5-indicator-score">
          {score}
          <span className="atlas-f5-indicator-max">/100</span>
        </span>
      </header>
      <div className="atlas-f5-indicator-body">{children}</div>
    </article>
  );
}

// ---------------------------------------------------------------------------
// Individual indicator cards
// ---------------------------------------------------------------------------

function InsiderActivityCard({ insider }: { insider: InsiderActivityIndicator }) {
  const activityTone = ACTIVITY_TONE[insider.activity_label] ?? 'is-muted';
  const activityLabel = insider.activity_label.replace(/_/g, ' ');

  return (
    <IndicatorCard label="Insider Activity" score={insider.score} weight={insider.weight}>
      <dl className="atlas-f5-dl">
        <div className="atlas-f5-dl-row">
          <dt>Signal</dt>
          <dd className={activityTone} data-testid="f5-insider-label">
            {activityLabel}
          </dd>
        </div>
        {insider.net_buy_value !== null && (
          <div className="atlas-f5-dl-row">
            <dt>Net Buys</dt>
            <dd className="is-green">{formatUsd(insider.net_buy_value)}</dd>
          </div>
        )}
        {insider.net_sell_value !== null && (
          <div className="atlas-f5-dl-row">
            <dt>Net Sells</dt>
            <dd className="is-red">{formatUsd(insider.net_sell_value)}</dd>
          </div>
        )}
        {insider.ceo_cfo_sell_value !== null && (
          <div className="atlas-f5-dl-row">
            <dt>CEO/CFO Sell</dt>
            <dd className="is-red">{formatUsd(insider.ceo_cfo_sell_value)}</dd>
          </div>
        )}
        <div className="atlas-f5-dl-row">
          <dt>Transactions</dt>
          <dd>{insider.transaction_count > 0 ? insider.transaction_count : '—'}</dd>
        </div>
      </dl>
    </IndicatorCard>
  );
}

function AltmanZCard({ altman }: { altman: AltmanZScoreIndicator }) {
  const zoneTone = ZONE_TONE[altman.zone] ?? 'is-muted';

  return (
    <IndicatorCard label="Altman Z-Score" score={altman.score} weight={altman.weight}>
      <dl className="atlas-f5-dl">
        <div className="atlas-f5-dl-row">
          <dt>Z-Score</dt>
          <dd className={zoneTone} data-testid="f5-altman-z">
            {altman.z_score !== null ? altman.z_score.toFixed(2) : '—'}
          </dd>
        </div>
        <div className="atlas-f5-dl-row">
          <dt>Zone</dt>
          <dd className={zoneTone}>{altman.zone}</dd>
        </div>
        {altman.x1_working_capital_ratio !== null && (
          <div className="atlas-f5-dl-row">
            <dt>X1 Wkg Cap</dt>
            <dd>{altman.x1_working_capital_ratio.toFixed(3)}</dd>
          </div>
        )}
        {altman.x4_market_cap_to_liabilities !== null && (
          <div className="atlas-f5-dl-row">
            <dt>X4 MktCap/Liab</dt>
            <dd>{altman.x4_market_cap_to_liabilities.toFixed(3)}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function FreeCashFlowCard({ fcf }: { fcf: FreeCashFlowIndicator }) {
  const trendTone = FCF_TONE[fcf.fcf_trend] ?? 'is-muted';
  const trendLabel = fcf.fcf_trend.replace(/_/g, ' ');

  return (
    <IndicatorCard label="Free Cash Flow" score={fcf.score} weight={fcf.weight}>
      <dl className="atlas-f5-dl">
        <div className="atlas-f5-dl-row">
          <dt>Trend</dt>
          <dd className={trendTone} data-testid="f5-fcf-trend">
            {trendLabel}
          </dd>
        </div>
        {fcf.fcf_current !== null && (
          <div className="atlas-f5-dl-row">
            <dt>Current Q</dt>
            <dd className={fcf.fcf_current >= 0 ? 'is-green' : 'is-red'}>
              {formatUsd(fcf.fcf_current)}
            </dd>
          </div>
        )}
        {fcf.fcf_prior !== null && (
          <div className="atlas-f5-dl-row">
            <dt>Prior Q</dt>
            <dd className={fcf.fcf_prior >= 0 ? '' : 'is-red'}>{formatUsd(fcf.fcf_prior)}</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function DebtEquityCard({ de }: { de: DebtEquityIndicator }) {
  return (
    <IndicatorCard label="Debt / Equity" score={de.score} weight={de.weight}>
      <dl className="atlas-f5-dl">
        <div className="atlas-f5-dl-row">
          <dt>D/E Ratio</dt>
          <dd className={deTone(de.ratio)} data-testid="f5-de-ratio">
            {de.ratio !== null ? de.ratio.toFixed(2) : '—'}
          </dd>
        </div>
        {de.total_debt !== null && (
          <div className="atlas-f5-dl-row">
            <dt>Total Debt</dt>
            <dd>{formatUsd(de.total_debt)}</dd>
          </div>
        )}
        {de.total_equity !== null && (
          <div className="atlas-f5-dl-row">
            <dt>Equity</dt>
            <dd className={de.total_equity >= 0 ? 'is-green' : 'is-red'}>
              {formatUsd(de.total_equity)}
            </dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

function InstitutionalOwnershipCard({ inst }: { inst: InstitutionalOwnershipIndicator }) {
  const labelTone = INST_TONE[inst.change_label] ?? 'is-muted';
  const labelText = inst.change_label.replace(/_/g, ' ');

  return (
    <IndicatorCard label="Institutional Ownership" score={inst.score} weight={inst.weight}>
      <dl className="atlas-f5-dl">
        <div className="atlas-f5-dl-row">
          <dt>Signal</dt>
          <dd className={labelTone} data-testid="f5-inst-label">
            {labelText}
          </dd>
        </div>
        {inst.ownership_pct !== null && (
          <div className="atlas-f5-dl-row">
            <dt>Ownership</dt>
            <dd className={labelTone}>{(inst.ownership_pct * 100).toFixed(1)}%</dd>
          </div>
        )}
      </dl>
    </IndicatorCard>
  );
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatUsd(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

// ---------------------------------------------------------------------------
// Tone helpers
// ---------------------------------------------------------------------------

function deTone(ratio: number | null): string {
  if (ratio === null) return '';
  if (ratio < 0.3) return 'is-green';
  if (ratio < 0.6) return 'is-cyan';
  if (ratio < 1.0) return 'is-yellow';
  if (ratio < 2.0) return 'is-orange';
  return 'is-red';
}
