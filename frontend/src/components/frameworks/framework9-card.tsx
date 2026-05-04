'use client';

import { cn } from '@/lib/utils';
import { useFramework9 } from '@/lib/hooks/use-framework9';
import type {
  DataSourceStatus,
  FlowDirection,
  Framework9Result,
  SignalTier,
} from '@/lib/schemas/framework9';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Severity badge class map. */
const SEVERITY_CLASS: Record<string, string> = {
  NONE: 'is-f9-green',
  PARTIAL: 'is-f9-amber',
  MAJOR: 'is-f9-red',
  CRITICAL: 'is-f9-red',
};

/** Signal tier labels. */
const TIER_LABEL: Record<SignalTier, string> = {
  TIER_1_WHALE: 'Tier 1 — Whale Block',
  TIER_2_INSTITUTIONAL: 'Tier 2 — Institutional',
  TIER_3_UNUSUAL: 'Tier 3 — Unusual Volume',
  TIER_4_WEAK: 'Tier 4 — Weak Signal',
  TIER_5_NONE: 'Tier 5 — No Signal',
};

/** Flow direction labels. */
const FLOW_LABEL: Record<FlowDirection, string> = {
  BULLISH: '↑ Bullish',
  BEARISH: '↓ Bearish',
  NEUTRAL: '→ Neutral',
  MIXED: '⟷ Mixed',
};

/** Data source status chip classes. */
const SOURCE_CHIP_CLASS: Record<DataSourceStatus, string> = {
  ONLINE: 'is-f9-src-online',
  PARTIAL: 'is-f9-src-partial',
  STALE: 'is-f9-src-stale',
  RATE_LIMITED: 'is-f9-src-stale',
  OFFLINE: 'is-f9-src-offline',
};

/** Warning level top-border class. */
const WARNING_BORDER: Record<string, string> = {
  NONE: '',
  AMBER: 'atlas-f9-warning-amber',
  RED: 'atlas-f9-warning-red',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatUsd(usd: number): string {
  if (usd >= 1_000_000_000) return `$${(usd / 1_000_000_000).toFixed(1)}B`;
  if (usd >= 1_000_000) return `$${(usd / 1_000_000).toFixed(1)}M`;
  if (usd >= 1_000) return `$${Math.round(usd / 1_000)}K`;
  return `$${usd.toFixed(0)}`;
}

function formatRatio(ratio: number | null): string {
  if (ratio === null) return '—';
  return ratio.toFixed(2);
}

function formatPct(n: number | null): string {
  if (n === null) return '—';
  return `${(n * 100).toFixed(1)}%`;
}

function formatSpread(sp: number | null): string {
  if (sp === null) return '—';
  const pct = (sp * 100).toFixed(0);
  if (sp > 0.6) return `${pct}% (buy-side)`;
  if (sp < 0.4) return `${pct}% (sell-side)`;
  return `${pct}% (mid)`;
}

function modifierLabel(mod: number): string {
  if (mod === 0) return '±0';
  return mod > 0 ? `+${mod}` : `${mod}`;
}

// ---------------------------------------------------------------------------
// Prop types
// ---------------------------------------------------------------------------

type Framework9CardProps = {
  /** Active ticker driven by the global framework ticker selector. */
  ticker: string;
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SourceChip({
  label,
  status,
}: {
  label: string;
  status: DataSourceStatus;
}) {
  return (
    <span
      className={cn('atlas-f9-src-chip', SOURCE_CHIP_CLASS[status])}
      title={`${label}: ${status}`}
    >
      {label} <span className="atlas-f9-src-dot" />
    </span>
  );
}

function StatCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="atlas-f9-stat-card">
      <span className="atlas-f9-stat-label">{label}</span>
      <span className="atlas-f9-stat-value">{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 9 — Options Flow Signal Hierarchy card.
 *
 * Sections:
 *   1. Header + source status chips (UW / POLYGON / AV)
 *   2. Data gap alert box (only when severity ≠ NONE)
 *   3. F4 score badge + grade + tier
 *   4. Four stat cards (F4 score / flow / largest print / P/C ratio)
 *   5. Dark pool panel (spread position + direction)
 *   6. Score breakdown (base + modifiers, skipped in grey)
 *   7. Active warning messages
 *   8. Expandable source status legend
 */
export function Framework9Card({ ticker }: Framework9CardProps) {
  const { data, isLoading, isError, error } = useFramework9(ticker);
  const hasData = ticker.trim().length > 0 && data !== undefined;
  const errorMsg =
    error instanceof Error ? error.message : 'Failed to load options flow data.';

  return (
    <section
      className={cn(
        'atlas-frameworks-panel atlas-fws-panel atlas-f9-panel',
        hasData && WARNING_BORDER[data.warning_level],
      )}
      data-testid="framework9-card"
    >
      {/* ── Section 1: Header + source chips ── */}
      <header className="atlas-f9-header">
        <div className="atlas-f9-header-left">
          <h2 className="atlas-frameworks-panel-title">Framework 9</h2>
          <span className="atlas-fws-subtitle">Options Flow Signal Hierarchy</span>
        </div>
        {hasData && (
          <div className="atlas-f9-src-chips" data-testid="f9-source-chips">
            <SourceChip label="UW" status={data.uw_status} />
            <SourceChip label="POLY" status={data.polygon_status} />
            <SourceChip label="AV" status={data.av_status} />
          </div>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="f9-loading">
            Loading options flow…
          </p>
        )}

        {isError && (
          <p className="atlas-fws-state-msg atlas-fws-state-error" data-testid="f9-error">
            {errorMsg}
          </p>
        )}

        {!ticker.trim() && !isLoading && (
          <p className="atlas-fws-state-msg" data-testid="f9-no-ticker">
            Select a ticker to view options flow.
          </p>
        )}

        {hasData && (
          <>
            {/* ── Section 2: Data gap alert ── */}
            {data.data_gap_severity !== 'NONE' && (
              <div
                className={cn(
                  'atlas-f9-gap-alert',
                  SEVERITY_CLASS[data.data_gap_severity],
                )}
                data-testid="f9-gap-alert"
              >
                <span className="atlas-f9-gap-badge">
                  {data.f1_propagation_badge ?? data.data_gap_severity}
                </span>
                {data.f1_propagation_message && (
                  <p className="atlas-f9-gap-msg">{data.f1_propagation_message}</p>
                )}
                {data.data_gaps.length > 0 && (
                  <ul className="atlas-f9-gap-list">
                    {data.data_gaps.map((gap, idx) => (
                      <li key={idx} className="atlas-f9-gap-item">
                        <strong>{gap.field}</strong> ({gap.source}): {gap.reason}
                        <br />
                        <em>{gap.impact}</em>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {/* ── Section 3: F4 score badge ── */}
            <div className="atlas-f9-score-row" data-testid="f9-score-row">
              <div className="atlas-f9-score-badge">
                <span className="atlas-f9-score-number">{data.f4_score.toFixed(0)}</span>
                <span className="atlas-f9-score-grade">{data.f4_grade}</span>
              </div>
              <div className="atlas-f9-tier-info">
                <span className="atlas-f9-tier-label">
                  {TIER_LABEL[data.signal_tier]}
                </span>
                <span
                  className={cn(
                    'atlas-f9-severity-chip',
                    SEVERITY_CLASS[data.data_gap_severity],
                  )}
                >
                  {data.data_gap_severity}
                </span>
              </div>
            </div>

            {/* ── Section 4: Stat cards ── */}
            <div className="atlas-f9-stats-grid" data-testid="f9-stats-grid">
              <StatCard label="F4 Score" value={data.f4_score.toFixed(0)} />
              <StatCard
                label="Flow Direction"
                value={FLOW_LABEL[data.flow_direction]}
              />
              <StatCard
                label="Largest Print"
                value={
                  data.largest_print_usd !== null
                    ? formatUsd(data.largest_print_usd)
                    : '—'
                }
              />
              <StatCard
                label="Call / Put Ratio"
                value={formatRatio(data.put_call_ratio)}
              />
            </div>

            {/* ── Section 5: Dark pool panel ── */}
            <div className="atlas-f9-dark-pool" data-testid="f9-dark-pool">
              <h3 className="atlas-f9-section-title">Dark Pool</h3>
              <div className="atlas-f9-dp-row">
                <span className="atlas-f9-dp-label">Spread Position</span>
                <span className="atlas-f9-dp-value">
                  {formatSpread(data.dark_pool_spread_position)}
                </span>
              </div>
              <div className="atlas-f9-dp-row">
                <span className="atlas-f9-dp-label">Direction</span>
                <span className="atlas-f9-dp-value">
                  {data.dark_pool_direction ?? '—'}
                </span>
              </div>
              {data.options_volume_vs_adv !== null && (
                <div className="atlas-f9-dp-row">
                  <span className="atlas-f9-dp-label">Volume vs ADV</span>
                  <span className="atlas-f9-dp-value">
                    {formatPct(data.options_volume_vs_adv)}
                  </span>
                </div>
              )}
            </div>

            {/* ── Section 6: Score breakdown ── */}
            <div className="atlas-f9-breakdown" data-testid="f9-breakdown">
              <h3 className="atlas-f9-section-title">Score Breakdown</h3>
              {typeof data.breakdown.base_score === 'number' && (
                <div className="atlas-f9-breakdown-row">
                  <span>Base ({data.breakdown.tier as string})</span>
                  <span>{(data.breakdown.base_score as number).toFixed(0)}</span>
                </div>
              )}
              <div className="atlas-f9-breakdown-row">
                <span>Put/Call modifier</span>
                <span
                  className={cn(
                    data.modifiers_skipped.includes('put_call') && 'atlas-f9-skipped',
                  )}
                >
                  {data.modifiers_skipped.includes('put_call')
                    ? 'skipped'
                    : modifierLabel(data.put_call_modifier)}
                </span>
              </div>
              <div className="atlas-f9-breakdown-row">
                <span>Dark pool modifier</span>
                <span
                  className={cn(
                    data.modifiers_skipped.includes('dark_pool') && 'atlas-f9-skipped',
                  )}
                >
                  {data.modifiers_skipped.includes('dark_pool')
                    ? 'skipped'
                    : modifierLabel(data.dark_pool_modifier)}
                </span>
              </div>
              {data.pre_earnings_reduction && (
                <div className="atlas-f9-breakdown-row atlas-f9-breakdown-warning">
                  <span>Pre-earnings reduction</span>
                  <span>{modifierLabel(data.pre_earnings_modifier)}</span>
                </div>
              )}
              <div className="atlas-f9-breakdown-row atlas-f9-breakdown-total">
                <span>F4 Score</span>
                <span>{data.f4_score.toFixed(0)}</span>
              </div>
            </div>

            {/* ── Section 7: Active flags ── */}
            {data.warning_messages.length > 0 && (
              <div className="atlas-f9-flags" data-testid="f9-flags">
                <h3 className="atlas-f9-section-title">Warnings</h3>
                <ul className="atlas-f9-flag-list">
                  {data.warning_messages.map((msg, idx) => (
                    <li key={idx} className="atlas-f9-flag-item">
                      {msg}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* ── Section 8: Source status detail ── */}
            <details className="atlas-f9-source-detail" data-testid="f9-source-detail">
              <summary className="atlas-f9-source-summary">Source status</summary>
              <dl className="atlas-f9-source-dl">
                <dt>Unusual Whales</dt>
                <dd>{data.uw_status}</dd>
                <dt>Polygon.io</dt>
                <dd>{data.polygon_status}</dd>
                <dt>Alpha Vantage</dt>
                <dd>{data.av_status}</dd>
              </dl>
              {data.f1_propagation_tooltip && (
                <p className="atlas-f9-tooltip-text">{data.f1_propagation_tooltip}</p>
              )}
            </details>
          </>
        )}
      </div>
    </section>
  );
}
