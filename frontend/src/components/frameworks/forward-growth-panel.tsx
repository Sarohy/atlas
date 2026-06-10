'use client';

import { cn } from '@/lib/utils';
import { useForwardGrowth } from '@/lib/hooks/use-forward-growth';
import { useFundamental } from '@/lib/hooks/use-fundamental';
import { useOptionsFlow } from '@/lib/hooks/use-options-flow';
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
  AVOID: 'AVOID',
};

const BUCKET_TONE: Record<GrowthBucket, string> = {
  CORE_COMPOUNDER: 'is-green',
  QUALITY_HOLD: 'is-teal',
  GROWTH_TACTICAL: 'is-yellow',
  STORY_RISK: 'is-red',
  AVOID: 'is-red',
};

function fmtPct(value: number | null | undefined): string {
  if (value == null) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
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
        {hasData && (
          <span
            className={cn('atlas-frameworks-pill atlas-fws-action-pill', GRADE_TONE[data.fgs_grade])}
            data-testid="fgs-grade-chip"
          >
            {data.fgs_grade}
          </span>
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
        {!isLoading && !isError && hasData && <FgsContent data={data} />}
        {!isLoading && !isError && !hasData && ticker.trim().length > 0 && (
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

function FgsContent({ data }: { data: ForwardGrowthResponse }) {
  const ra = data.revenue_acceleration;
  const gap = (source: string) => (source === 'DATA_GAP' ? ' (gap)' : '');
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

      <div className="atlas-fws-breakdown-divider" />

      {/* Sub-factors */}
      <Row
        label="Revenue acceleration"
        value={`${ra.score}${gap(ra.source)} · YoY ${fmtPct(ra.yoy_pct)}${
          ra.accelerating == null ? '' : ra.accelerating ? ' ↑' : ' ↓'
        }`}
      />
      <Row label="Backlog / bookings" value={`${data.backlog_bookings.score}${gap(data.backlog_bookings.source)}`} />
      <Row label="Customer quality" value={`${data.customer_quality.score}${gap(data.customer_quality.source)}`} />
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
