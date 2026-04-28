'use client';

import { useState } from 'react';

import { useFramework12 } from '@/lib/hooks/use-framework12';
import {
  useSection16,
  useUseOverride,
} from '@/lib/hooks/use-section16';
import type { Framework12Result } from '@/lib/schemas/framework12';
import type {
  GateResult,
  Rule1Result,
  Rule2Result,
  Rule3Result,
  Rule4Result,
  Section16Result,
} from '@/lib/schemas/section16';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default operator name attached to mutations — single-investor system. */
const OPERATOR_NAME = 'investor';

const GATE_LABEL: Record<GateResult, string> = {
  PASS: 'PASS',
  FAIL: 'FAIL',
  UNKNOWN: 'UNKNOWN',
};

const GATE_CHIP_CLASS: Record<GateResult, string> = {
  PASS: 'is-s16-pass',
  FAIL: 'is-s16-fail',
  UNKNOWN: 'is-s16-unknown',
};

const TRACK_LABEL: Record<TrackType, string> = {
  TRACK_A: 'Track A',
  TRACK_B: 'Track B',
  UNASSIGNED: 'Unassigned',
};

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatUsd(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—';
  if (Math.abs(val) >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
  return `$${val.toFixed(0)}`;
}

function formatPct(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—';
  return `${val.toFixed(2)}%`;
}

function formatPrice(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—';
  return `$${val.toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Sub-components — Section 16 panel
// ---------------------------------------------------------------------------

function RuleChip({ label, result }: { label: string; result: GateResult | undefined }) {
  if (result === undefined) {
    return (
      <span
        className="atlas-s16-rule-chip is-s16-na"
        data-testid={`s16-rule-chip-${label.toLowerCase()}`}
      >
        <span className="atlas-s16-rule-chip-label">{label}</span>
        <span className="atlas-s16-rule-chip-value">N/A</span>
      </span>
    );
  }
  return (
    <span
      className={cn('atlas-s16-rule-chip', GATE_CHIP_CLASS[result])}
      data-testid={`s16-rule-chip-${label.toLowerCase()}`}
    >
      <span className="atlas-s16-rule-chip-label">{label}</span>
      <span className="atlas-s16-rule-chip-value">{GATE_LABEL[result]}</span>
    </span>
  );
}

function Rule1Detail({ rule }: { rule: Rule1Result }) {
  return (
    <div className="atlas-s16-rule-detail">
      <span className="atlas-s16-rule-line">{rule.reason}</span>
      <span className="atlas-s16-rule-line">
        Dark pool: {formatUsd(rule.dark_pool_usd)} · Flow: {formatUsd(rule.flow_usd)} · DTE:{' '}
        {rule.days_to_earnings ?? '—'}
      </span>
    </div>
  );
}

function Rule2Detail({ rule }: { rule: Rule2Result }) {
  return (
    <div className="atlas-s16-rule-detail">
      <span className="atlas-s16-rule-line">{rule.reason}</span>
      <span className="atlas-s16-rule-line">
        Earnings: {rule.earnings_date ?? '—'} · DTE: {rule.days_to_earnings ?? '—'} · Max:{' '}
        {rule.catalyst_max_days}d
        {rule.parabolic_window ? ' · parabolic-window' : ''}
      </span>
    </div>
  );
}

function Rule3Detail({ rule }: { rule: Rule3Result }) {
  return (
    <div className="atlas-s16-rule-detail">
      <span className="atlas-s16-rule-line">{rule.reason}</span>
      <span className="atlas-s16-rule-line">
        Price: {formatPrice(rule.current_price)} · 365d high: {formatPrice(rule.high_365d)} · Below
        high: {formatPct(rule.pct_below_high)}
      </span>
      {rule.local_high != null && (
        <span className="atlas-s16-rule-line">
          Local high ({rule.local_high_lookback_bars}d): {formatPrice(rule.local_high)} · Below
          local high: {formatPct(rule.pct_below_local_high)}
        </span>
      )}
    </div>
  );
}

function Rule4Detail({ rule }: { rule: Rule4Result }) {
  return (
    <div className="atlas-s16-rule-detail">
      <span className="atlas-s16-rule-line">{rule.reason}</span>
      <span className="atlas-s16-rule-line">
        Set by: {rule.set_by ?? '—'} · Date: {rule.fit_date ?? '—'}
      </span>
    </div>
  );
}

function OverrideBlock({
  ticker,
  data,
}: {
  ticker: string;
  data: Section16Result;
}) {
  const ov = data.override;
  const mutation = useUseOverride(ticker);
  if (!ov) return null;
  return (
    <div className="atlas-s16-override-block" data-testid="s16-override-block">
      <span className="atlas-s16-override-title">Override (Track A)</span>
      <span className="atlas-s16-override-reason">{ov.reason}</span>
      <span className="atlas-s16-override-meta">
        Available: {ov.available ? 'yes' : 'no'} · Qualifies: {ov.qualifies ? 'yes' : 'no'} · Used
        in cycle: {ov.used_in_cycle ? 'yes' : 'no'}
      </span>
      <button
        type="button"
        className="atlas-s16-btn"
        disabled={
          mutation.isPending ||
          !ov.available ||
          !ov.qualifies ||
          ov.used_in_cycle ||
          data.override_used
        }
        onClick={() => mutation.mutate({ used_by: OPERATOR_NAME })}
        data-testid="s16-use-override"
      >
        Use override now
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 16 panel
// ---------------------------------------------------------------------------

function Section16Panel({ ticker }: { ticker: string }) {
  const { data, isLoading, isError, error } = useSection16(ticker);
  const [showDetail, setShowDetail] = useState(false);
  const errorMsg = error instanceof Error ? error.message : 'Failed to load Section 16.';

  return (
    <div className="atlas-s16-panel" data-testid="section16-panel">
      <header className="atlas-s16-panel-header">
        <div className="atlas-s16-panel-header-left">
          <h3 className="atlas-s16-panel-title">Section 16 — Entry Gatekeeper</h3>
          {data && (
            <span className="atlas-s16-track-badge" data-testid="s16-track-badge">
              {TRACK_LABEL[data.track]}
            </span>
          )}
        </div>
        {data && (
          <span
            className={cn('atlas-s16-gate-chip', GATE_CHIP_CLASS[data.gate])}
            data-testid="s16-gate-chip"
          >
            {GATE_LABEL[data.gate]}
            {data.override_used ? ' (override)' : ''}
          </span>
        )}
      </header>

      <div className="atlas-s16-panel-body">
        {isLoading && <p className="atlas-s16-state-msg">Evaluating…</p>}
        {isError && (
          <p className="atlas-s16-state-msg atlas-s16-state-msg--error" data-testid="s16-error">
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && data && (
          <>
            <div className="atlas-s16-rule-chip-row" data-testid="s16-rule-chip-row">
              <RuleChip label="Rule 1" result={data.rule1?.result} />
              <RuleChip label="Rule 2" result={data.rule2?.result} />
              <RuleChip label="Rule 3" result={data.rule3?.result} />
              <RuleChip label="Rule 4" result={data.rule4?.result} />
            </div>

            <button
              type="button"
              className="atlas-s16-detail-toggle"
              onClick={() => setShowDetail((v) => !v)}
              data-testid="s16-toggle-detail"
            >
              {showDetail ? 'Hide rule detail' : 'Show rule detail'}
            </button>

            {showDetail && (
              <div className="atlas-s16-rule-details" data-testid="s16-rule-details">
                {data.rule1 && (
                  <div className="atlas-s16-rule-block">
                    <span className="atlas-s16-rule-block-title">Rule 1 — Conviction signal</span>
                    <Rule1Detail rule={data.rule1} />
                  </div>
                )}
                {data.rule2 && (
                  <div className="atlas-s16-rule-block">
                    <span className="atlas-s16-rule-block-title">Rule 2 — Catalyst horizon</span>
                    <Rule2Detail rule={data.rule2} />
                  </div>
                )}
                {data.rule3 && (
                  <div className="atlas-s16-rule-block">
                    <span className="atlas-s16-rule-block-title">Rule 3 — Price position</span>
                    <Rule3Detail rule={data.rule3} />
                  </div>
                )}
                {data.rule4 && (
                  <div className="atlas-s16-rule-block">
                    <span className="atlas-s16-rule-block-title">Rule 4 — Portfolio fit</span>
                    <Rule4Detail rule={data.rule4} />
                  </div>
                )}
              </div>
            )}

            <OverrideBlock ticker={ticker} data={data} />
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Framework 12 panel
// ---------------------------------------------------------------------------

const F12_STATUS_CLASS: Record<Framework12Result['status'], string> = {
  SIZED: 'is-f12-sized',
  WATCHLIST: 'is-f12-watchlist',
  BLOCKED: 'is-f12-blocked',
  UNKNOWN: 'is-f12-unknown',
};

function Framework12Panel({ ticker }: { ticker: string }) {
  const { data, isLoading, isError, error } = useFramework12(ticker);
  const errorMsg = error instanceof Error ? error.message : 'Failed to load Framework 12.';

  return (
    <div className="atlas-f12-panel" data-testid="framework12-panel">
      <header className="atlas-f12-panel-header">
        <h3 className="atlas-f12-panel-title">Framework 12 — Decision Matrix</h3>
        {data && (
          <span
            className={cn('atlas-f12-status-chip', F12_STATUS_CLASS[data.status])}
            data-testid="f12-status-chip"
          >
            {data.status}
          </span>
        )}
      </header>

      <div className="atlas-f12-panel-body">
        {isLoading && <p className="atlas-f12-state-msg">Evaluating…</p>}
        {isError && (
          <p className="atlas-f12-state-msg atlas-f12-state-msg--error" data-testid="f12-error">
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && data && <Framework12Body data={data} />}
      </div>
    </div>
  );
}

function Framework12Body({ data }: { data: Framework12Result }) {
  if (data.status === 'BLOCKED' || data.matched_row === null) {
    return (
      <div className="atlas-f12-blocked" data-testid="f12-blocked">
        <span className="atlas-f12-blocked-label">No sizing — gate not passed</span>
        <span className="atlas-f12-blocked-reason">
          {data.blocked_reason ?? 'No matching priority row.'}
        </span>
        <span className="atlas-f12-meta">NAV: {formatUsd(data.current_nav_usd)}</span>
      </div>
    );
  }

  const row = data.matched_row;
  return (
    <div className="atlas-f12-sizing" data-testid="f12-sizing">
      <div className="atlas-f12-priority-row">
        <span className="atlas-f12-priority-code">{row.priority_code}</span>
        <span className="atlas-f12-priority-label">{row.priority_label}</span>
      </div>

      <div className="atlas-f12-size-block">
        <span className="atlas-f12-size-range" data-testid="f12-size-range">
          {formatUsd(data.size_min_usd)} – {formatUsd(data.size_max_usd)}
        </span>
        <span className="atlas-f12-size-pct">
          {row.size_min_pct.toFixed(2)}% – {row.size_max_pct.toFixed(2)}% of NAV
        </span>
      </div>

      <div className="atlas-f12-timing">
        <span className="atlas-f12-timing-label">Timing:</span>
        <span className="atlas-f12-timing-rule" data-testid="f12-timing-rule">
          {data.timing_rule ?? row.timing_rule}
        </span>
      </div>

      <div className="atlas-f12-meta-row">
        <span className="atlas-f12-meta">NAV: {formatUsd(data.current_nav_usd)}</span>
        {row.is_watchlist_only && (
          <span className="atlas-f12-meta is-f12-meta-warn">Watchlist only</span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Combined card (public)
// ---------------------------------------------------------------------------

type Section16Framework12CardProps = {
  ticker: string;
};

/**
 * Combined Section 16 (entry gate) + Framework 12 (sizing) card.
 *
 * Renders two side-by-side panels:
 *   1. Section 16 — gate verdict, per-rule chips, override, operator controls.
 *   2. Framework 12 — sizing range, priority match, timing rule.
 *
 * All market data fetched live on every evaluation (no caching).
 */
export function Section16Framework12Card({ ticker }: Section16Framework12CardProps) {
  if (!ticker) {
    return (
      <section
        className="atlas-frameworks-panel atlas-fws-panel atlas-s16-f12-card"
        data-testid="section16-framework12-card"
      >
        <p className="atlas-fws-state-msg">Select a ticker to evaluate the entry gate.</p>
      </section>
    );
  }

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-s16-f12-card"
      data-testid="section16-framework12-card"
    >
      <header className="atlas-s16-f12-header">
        <div>
          <h2 className="atlas-frameworks-panel-title">Entry Gate &amp; Sizing</h2>
          <span className="atlas-fws-subtitle">
            Section 16 → Framework 12 · {ticker}
          </span>
        </div>
      </header>

      <div className="atlas-s16-f12-body">
        <Section16Panel ticker={ticker} />
        <Framework12Panel ticker={ticker} />
      </div>
    </section>
  );
}
