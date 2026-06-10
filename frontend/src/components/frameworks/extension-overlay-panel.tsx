'use client';

import { cn } from '@/lib/utils';
import { useExtensionOverlay } from '@/lib/hooks/use-extension-overlay';
import type {
  ExtensionFlag,
  ExtensionOverlayResponse,
  OverlayAction,
} from '@/lib/schemas/extension-overlay';

// ---------------------------------------------------------------------------
// Display maps
// ---------------------------------------------------------------------------

const FLAG_TONE: Record<ExtensionFlag, string> = {
  GREEN: 'is-green',
  YELLOW: 'is-yellow',
  RED: 'is-red',
  EXTREME_RED: 'is-red',
};

const FLAG_LABEL: Record<ExtensionFlag, string> = {
  GREEN: 'GREEN',
  YELLOW: 'YELLOW',
  RED: 'RED',
  EXTREME_RED: 'EXTREME RED',
};

const ACTION_LABEL: Record<OverlayAction, string> = {
  ADD: 'ADD',
  BUY_ON_PULLBACK: 'BUY ON PULLBACK',
  HOLD_TRIM: 'HOLD / TRIM',
  TRIM_HEDGE: 'TRIM / HEDGE',
  AVOID: 'AVOID',
};

const ACTION_TONE: Record<OverlayAction, string> = {
  ADD: 'is-green',
  BUY_ON_PULLBACK: 'is-yellow',
  HOLD_TRIM: 'is-red',
  TRIM_HEDGE: 'is-red',
  AVOID: 'is-red',
};

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function fmtPct(value: number | null | undefined, decimals = 1): string {
  if (value == null) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

function fmtNum(value: number | null | undefined, decimals = 1): string {
  if (value == null) return '—';
  return value.toFixed(decimals);
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type ExtensionOverlayPanelProps = {
  ticker: string;
  /** Regime-adjusted F1 display score — drives the action matrix (quality x timing). */
  atlasScore: number | undefined;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Overbought / Extension Overlay — a standalone card (sits above Forward Growth,
 * beside Framework 1).
 *
 * A name can be fundamentally elite and still be a bad entry today. This card
 * surfaces the technical extension picture (RSI, recent moves, distance from
 * the MAs, gap) as a 0-N Extension Risk Score + Green/Yellow/Red flag, and —
 * using the regime-adjusted conviction score — an action recommendation that
 * pairs quality with entry timing.
 */
export function ExtensionOverlayPanel({ ticker, atlasScore }: ExtensionOverlayPanelProps) {
  const { data, isLoading, isError, error } = useExtensionOverlay(ticker, atlasScore);
  const hasData = ticker.trim().length > 0 && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load extension data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel"
      data-testid="extension-overlay-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <div>
          <h2 className="atlas-frameworks-panel-title">Extension Overlay</h2>
          <span className="atlas-fws-subtitle">Overbought / entry-timing check</span>
        </div>
        {hasData && (
          <span
            className={cn(
              'atlas-frameworks-pill atlas-fws-action-pill',
              FLAG_TONE[data.extension_flag],
            )}
            data-testid="ext-flag-chip"
          >
            {FLAG_LABEL[data.extension_flag]}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="ext-loading">
            Computing extension…
          </p>
        )}
        {isError && (
          <p className="atlas-fws-state-msg atlas-fws-state-msg--error" data-testid="ext-error">
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && hasData && <OverlayContent data={data} />}
        {!isLoading && !isError && !hasData && ticker.trim().length > 0 && (
          <p className="atlas-fws-state-msg" data-testid="ext-empty">
            No extension data available for {ticker}.
          </p>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Content
// ---------------------------------------------------------------------------

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="atlas-fws-calc-row">
      <span className="atlas-fws-calc-label">{label}</span>
      <span className="atlas-fws-calc-value">{value}</span>
    </div>
  );
}

function OverlayContent({ data }: { data: ExtensionOverlayResponse }) {
  return (
    <div data-testid="ext-content">
      {/* Risk score headline */}
      <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
        <span className="atlas-fws-calc-label">Extension Risk Score</span>
        <span
          className={cn('atlas-fws-calc-value', FLAG_TONE[data.extension_flag])}
          data-testid="ext-risk-score"
        >
          {data.extension_risk_score}
        </span>
      </div>

      <div className="atlas-fws-breakdown-divider" />

      {/* Metrics */}
      <MetricRow label="RSI 14" value={fmtNum(data.rsi_14)} />
      <MetricRow label="RSI 7" value={fmtNum(data.rsi_7)} />
      <MetricRow label="14-day move" value={fmtPct(data.move_14d_pct)} />
      <MetricRow label="21-day move" value={fmtPct(data.move_21d_pct)} />
      <MetricRow label="vs 20-day MA" value={fmtPct(data.pct_above_20dma)} />
      <MetricRow label="vs 50-day MA" value={fmtPct(data.pct_above_50dma)} />
      <MetricRow label="vs 200-day MA" value={fmtPct(data.pct_above_200dma)} />
      <MetricRow label="Gap today" value={fmtPct(data.gap_today_pct)} />
      <MetricRow
        label="vs VWAP (daily)"
        value={data.pct_vs_vwap == null ? 'DATA GAP' : fmtPct(data.pct_vs_vwap)}
      />
      <MetricRow
        label="vs ATH"
        value={
          data.pct_from_ath == null
            ? 'DATA GAP'
            : `${fmtPct(data.pct_from_ath)}${data.ath != null ? ` ($${data.ath.toFixed(2)})` : ''}`
        }
      />
      <MetricRow label="IV rank" value={data.iv_rank == null ? 'DATA GAP' : fmtNum(data.iv_rank, 0)} />

      {/* Action */}
      <div className="atlas-fws-breakdown-divider" />
      <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
        <span className="atlas-fws-calc-label">Action</span>
        {data.action ? (
          <span
            className={cn('atlas-frameworks-pill atlas-fws-action-pill', ACTION_TONE[data.action])}
            data-testid="ext-action"
          >
            {ACTION_LABEL[data.action]}
          </span>
        ) : (
          <span className="atlas-fws-calc-value" data-testid="ext-action">
            —
          </span>
        )}
      </div>
      {data.action_detail && (
        <p className="atlas-fws-state-msg" data-testid="ext-action-detail">
          {data.action_detail}
        </p>
      )}
    </div>
  );
}
