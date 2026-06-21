'use client';

import { cn } from '@/lib/utils';
import { useForwardGrowth } from '@/lib/hooks/use-forward-growth';
import { useFrameworkScore } from '@/lib/hooks/use-framework-score';
import { useFundamental } from '@/lib/hooks/use-fundamental';
import { useOptionsFlow } from '@/lib/hooks/use-options-flow';
import type { EtfBranchMetadata } from '@/lib/schemas/framework-score';
import type {
  FgsGrade,
  ForwardGrowthResponse,
  GrowthBucket,
} from '@/lib/schemas/forward-growth';

// ---------------------------------------------------------------------------
// Display maps
// ---------------------------------------------------------------------------

const GRADE_TONE: Record<FgsGrade, string> = {
  ELITE: 'is-green',
  HIGH: 'is-teal',
  MODERATE: 'is-yellow',
  LOW: 'is-red',
};

const BUCKET_LABEL: Record<GrowthBucket, string> = {
  CORE_COMPOUNDER: 'CORE COMPOUNDER',
  QUALITY_HOLD: 'QUALITY HOLD',
  GROWTH_TACTICAL: 'GROWTH TACTICAL',
  STORY_RISK: 'STORY RISK',
  ADD_BLOCKED: 'HIGH GROWTH — ADD BLOCKED',
  AVOID: 'AVOID',
};

const BUCKET_TONE: Record<GrowthBucket, string> = {
  CORE_COMPOUNDER: 'is-green',
  QUALITY_HOLD: 'is-teal',
  GROWTH_TACTICAL: 'is-yellow',
  STORY_RISK: 'is-red',
  ADD_BLOCKED: 'is-yellow',
  AVOID: 'is-red',
};

function fmtPct(value: number | null | undefined): string {
  if (value == null) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function fmtBigUsd(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(0)}M`;
  return `$${value.toFixed(0)}`;
}

/** Exact largest-customer %, else a ">10% customer" count, from EDGAR. */
function fmtConcentration(pct: number | null | undefined, count: number | null | undefined): string {
  if (pct != null) return ` · top cust ${pct.toFixed(0)}%`;
  if (count != null) return ` · ${count} cust >10%`;
  return '';
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

type ForwardGrowthPanelProps = {
  ticker: string;
  /** ATLAS conviction score (F1 display score) — context for the action matrix. */
  atlasScore: number | undefined;
};

/**
 * Forward Growth Score (FGS) panel — a parallel axis to the ATLAS score.
 *
 * F5 asks "can this company survive and compound?"; FGS asks "can it grow much
 * faster than the market expects if the thesis works?". FGS is never blended
 * into the ATLAS number — it feeds the F5 x FGS x F4 action matrix (bucket).
 */
export function ForwardGrowthPanel({ ticker, atlasScore }: ForwardGrowthPanelProps) {
  // F5 (survivability) and F4 (flow) drive the action-matrix bucket.
  const { data: fundamental } = useFundamental(ticker);
  const { data: optionsFlow } = useOptionsFlow(ticker);
  const f5 = fundamental?.ticker?.toUpperCase() === ticker.trim().toUpperCase()
    ? fundamental?.f5_score
    : undefined;
  const f4 = optionsFlow?.ticker?.toUpperCase() === ticker.trim().toUpperCase()
    ? optionsFlow?.f4_score
    : undefined;

  const { data, isLoading, isError, error } = useForwardGrowth(ticker, {
    f5,
    f4,
    atlas: atlasScore,
  });
  // ETF/proxy detection: when the universal router classified this ticker as a
  // non-operating instrument, the DIRECT FGS is not applicable — suppress it and
  // show a look-through label instead of a misleading "AVOID — no edge" card.
  const { data: frameworkScore } = useFrameworkScore(ticker);
  const etfBranch =
    frameworkScore?.ticker?.toUpperCase() === ticker.trim().toUpperCase()
      ? (frameworkScore?.etf_branch ?? undefined)
      : undefined;
  const hasData = ticker.trim().length > 0 && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load forward-growth data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel"
      data-testid="forward-growth-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <div>
          <h2 className="atlas-frameworks-panel-title">Forward Growth</h2>
          <span className="atlas-fws-subtitle">FGS · growth potential (parallel axis)</span>
        </div>
        {etfBranch ? (
          <span
            className="atlas-frameworks-pill atlas-fws-action-pill is-teal"
            data-testid="fgs-grade-chip"
          >
            PROXY
          </span>
        ) : (
          hasData && (
            <span
              className={cn(
                'atlas-frameworks-pill atlas-fws-action-pill',
                GRADE_TONE[data.fgs_grade],
              )}
              data-testid="fgs-grade-chip"
            >
              {data.fgs_grade}
            </span>
          )
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="fgs-loading">
            Computing forward growth…
          </p>
        )}
        {isError && (
          <p className="atlas-fws-state-msg atlas-fws-state-msg--error" data-testid="fgs-error">
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && etfBranch && <EtfFgsView etfBranch={etfBranch} />}
        {!isLoading && !isError && !etfBranch && hasData && <FgsContent data={data} />}
        {!isLoading && !isError && !etfBranch && !hasData && ticker.trim().length > 0 && (
          <p className="atlas-fws-state-msg" data-testid="fgs-empty">
            No forward-growth data available for {ticker}.
          </p>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Content
// ---------------------------------------------------------------------------

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="atlas-fws-calc-row">
      <span className="atlas-fws-calc-label">{label}</span>
      <span className={cn('atlas-fws-calc-value', tone)}>{value}</span>
    </div>
  );
}

/**
 * ETF/proxy view: the DIRECT Forward Growth Score is not applicable to a
 * fund/basket instrument, so suppress it (it would otherwise read "AVOID — no
 * edge" off neutral fallbacks) and show the look-through growth label derived
 * from the ETF branch model instead.
 */
function EtfFgsView({ etfBranch }: { etfBranch: EtfBranchMetadata }) {
  const bullish = /bullish/i.test(etfBranch.headline_label);
  const lookThrough = bullish ? 'Bullish' : 'Mixed / watch';
  const tone = bullish ? 'is-green' : 'is-yellow';
  return (
    <div data-testid="fgs-etf-content">
      <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
        <span className="atlas-fws-calc-label">Direct FGS</span>
        <span className="atlas-fws-calc-value is-muted" data-testid="fgs-etf-direct-na">
          N/A — ETF/proxy instrument
        </span>
      </div>
      <Row
        label="Look-through growth"
        value={`${lookThrough} — ${etfBranch.label}`}
        tone={tone}
      />
      {etfBranch.holdings_driver && (
        <Row label="Holdings driver" value={etfBranch.holdings_driver} />
      )}
      <p className="atlas-fws-state-msg" data-testid="fgs-etf-note">
        Direct company growth factors do not apply to a basket instrument — growth is assessed
        through the proxy look-through model, not a single-name FGS.
      </p>
    </div>
  );
}

function FgsContent({ data }: { data: ForwardGrowthResponse }) {
  const ra = data.revenue_acceleration;
  // Annotate provenance: DATA_GAP → "(gap)", transcript heuristic → "(est)".
  const gap = (source: string) =>
    source === 'DATA_GAP' ? ' (gap)' : source === 'transcript' ? ' (est)' : '';
  return (
    <div data-testid="fgs-content">
      {/* FGS headline + confidence */}
      <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
        <span className="atlas-fws-calc-label">Forward Growth Score</span>
        <span
          className={cn('atlas-fws-calc-value', GRADE_TONE[data.fgs_grade])}
          data-testid="fgs-score"
        >
          {data.fgs_score}/100
        </span>
      </div>
      <Row label="Confidence (axes measured)" value={`${data.confidence_pct}%`} />

      {/* F5 ↔ FGS bridge: these are SEPARATE axes, not the same number. F5
          (Fundamental Quality) measures current survivability/quality; FGS
          measures forward growth potential. They diverge by design — a gap is
          expected, not a bug. */}
      {data.f5_score != null && (
        <>
          <Row
            label="F5 fundamental quality (separate axis)"
            value={`${data.f5_score}/100 · Δ ${
              data.fgs_score - data.f5_score >= 0 ? '+' : ''
            }${data.fgs_score - data.f5_score} vs FGS`}
          />
          <p className="atlas-fws-state-msg" data-testid="fgs-f5-bridge">
            FGS (forward growth) and F5 (current fundamental quality) are separate axes — a
            gap between them is expected, not a scoring error. FGS is never blended into F5 or
            the ATLAS framework score.
          </p>
        </>
      )}

      <div className="atlas-fws-breakdown-divider" />

      {/* Sub-factors */}
      <Row
        label="Revenue acceleration"
        value={`${ra.score}${gap(ra.source)} · YoY ${fmtPct(ra.yoy_pct)}${
          ra.accelerating == null ? '' : ra.accelerating ? ' ↑' : ' ↓'
        }`}
      />
      <Row
        label="Backlog / bookings"
        value={`${data.backlog_bookings.score}${gap(data.backlog_bookings.source)}${
          data.backlog_usd != null ? ` · ${fmtBigUsd(data.backlog_usd)} RPO` : ''
        }`}
      />
      <Row
        label="Customer quality"
        value={`${data.customer_quality.score}${gap(data.customer_quality.source)}${fmtConcentration(
          data.customer_concentration_pct,
          data.customers_over_10pct,
        )}`}
      />
      <Row label="Product ramp" value={`${data.product_ramp.score}${gap(data.product_ramp.source)}`} />
      <Row
        label="TAM / bottleneck"
        value={`${data.tam_bottleneck.score} · ${data.tam_bottleneck.wave}`}
      />

      {/* Action bucket (F5 x FGS x F4) */}
      <div className="atlas-fws-breakdown-divider" />
      <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
        <span className="atlas-fws-calc-label">Bucket (F5 × FGS × F4)</span>
        {data.bucket ? (
          <span
            className={cn('atlas-frameworks-pill atlas-fws-action-pill', BUCKET_TONE[data.bucket])}
            data-testid="fgs-bucket"
          >
            {BUCKET_LABEL[data.bucket]}
          </span>
        ) : (
          <span className="atlas-fws-calc-value" data-testid="fgs-bucket">
            —
          </span>
        )}
      </div>
      {data.action && (
        <p className="atlas-fws-state-msg" data-testid="fgs-action">
          {data.action}
        </p>
      )}
    </div>
  );
}
