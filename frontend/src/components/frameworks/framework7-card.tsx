'use client';

import { cn } from '@/lib/utils';
import { useFramework7 } from '@/lib/hooks/use-framework7';
import type { EarningsGate } from '@/lib/schemas/framework7';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Score threshold above which the 50% CAP applies. */
const SCORE_THRESHOLD = 80;

/** Total score bar width in abstract units (maps to 100%). */
const SCORE_BAR_MAX = 100;

/** Post-earnings sequence steps. */
const POST_EARNINGS_STEPS = [
  'Earnings reported',
  'F2 transcript',
  'F2 + F5 rescore',
  'New score',
  'Gate reopens',
] as const;

/** CSS class map keyed by status string. */
const STATUS_TONE: Record<string, string> = {
  OPEN: 'is-f7-green',
  CLOSED: 'is-f7-red',
  '50% CAP': 'is-f7-amber',
  'DOUBLE BLOCKED': 'is-f7-purple',
};

/** Main action text per status. */
const ACTION_TEXT: Record<string, string> = {
  OPEN: 'WINDOW OPEN',
  CLOSED: 'NO ADDS',
  '50% CAP': '50% CAP',
  'DOUBLE BLOCKED': 'DOUBLE BLOCKED',
};

// ---------------------------------------------------------------------------
// Prop types
// ---------------------------------------------------------------------------

type Framework7CardProps = {
  /** Active ticker driven by the global framework ticker selector. */
  ticker: string;
  /**
   * The regime-adjusted F1 display score (= final_score + modifier, clamped
   * 0-100). Passed directly to the backend so the gate evaluates the same
   * score the investor sees on the F1 panel.
   */
  adjustedScore: number | undefined;
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 7 — Earnings Gate Rule card.
 *
 * Displays the current earnings gate status for the active ticker, including:
 * - Status chip (OPEN / CLOSED / 50% CAP / DOUBLE BLOCKED)
 * - Earnings and gate-close dates
 * - Score vs 80-threshold bar
 * - Countdown bar from gate-close to earnings
 * - Rule explanation
 * - Post-earnings sequence
 */
export function Framework7Card({ ticker, adjustedScore }: Framework7CardProps) {
  const { data, isLoading, isError, error } = useFramework7(ticker, adjustedScore);
  const hasData = ticker.trim().length > 0 && data !== undefined;
  const errorMsg = error instanceof Error ? error.message : 'Failed to load gate data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-f7-panel"
      data-testid="framework7-card"
    >
      {/* ── Header ── */}
      <header className="atlas-f7-header">
        <div className="atlas-f7-header-left">
          <h2 className="atlas-frameworks-panel-title">Framework 7</h2>
          <span className="atlas-fws-subtitle">Earnings Gate Rule</span>
        </div>
        {hasData && (
          <span
            className={cn('atlas-f7-status-chip', STATUS_TONE[data.status] ?? 'is-f7-green')}
            data-testid="f7-status-chip"
          >
            {data.status}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="f7-loading">
            Evaluating earnings gate…
          </p>
        )}
        {isError && (
          <p className="atlas-fws-state-msg atlas-fws-state-msg--error" data-testid="f7-error">
            {errorMsg}
          </p>
        )}
        {!isLoading && !isError && hasData && <GateContent data={data} />}
        {!isLoading && !isError && !hasData && ticker.trim().length > 0 && (
          <p className="atlas-fws-state-msg" data-testid="f7-empty">
            No gate data available for {ticker}.
          </p>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Content
// ---------------------------------------------------------------------------

function GateContent({ data }: { data: EarningsGate }) {
  const toneClass = STATUS_TONE[data.status] ?? 'is-f7-green';
  const actionText = ACTION_TEXT[data.status] ?? data.status;

  return (
    <div className="atlas-f7-content" data-testid="f7-content">
      {/* ── Stat cards row ── */}
      <div className="atlas-f7-stats-row">
        <StatCard label="Earnings" value={data.earnings_date ?? '—'} />
        <StatCard label="Gate closes" value={data.gate_close_date ?? '—'} />
        <StatCard label="Score" value={String(data.final_score)} tone={toneClass} />
        <StatCard label="Gate" value={data.gate_active ? 'ACTIVE' : 'OPEN'} tone={toneClass} />
      </div>

      {/* ── Main action text ── */}
      <p
        className={cn('atlas-f7-action-text', toneClass)}
        data-testid="f7-action-text"
      >
        {actionText}
      </p>

      {/* ── Score vs threshold bar ── */}
      <ScoreBar score={data.final_score} toneClass={toneClass} />

      {/* ── Countdown bar ── */}
      {data.earnings_date && data.gate_close_date && (
        <CountdownBar
          gateCloseDate={data.gate_close_date}
          earningsDate={data.earnings_date}
          daysToEarnings={data.days_to_earnings}
        />
      )}

      {/* ── Rule explanation ── */}
      <RuleExplanation data={data} toneClass={toneClass} />

      {/* ── 50% CAP deployment boxes ── */}
      {data.status === '50% CAP' && <CapDeploymentBoxes />}

      {/* ── Post-earnings sequence ── */}
      <PostEarningsSequence />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="atlas-f7-stat-card">
      <span className="atlas-f7-stat-label">{label}</span>
      <span className={cn('atlas-f7-stat-value', tone)}>{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score bar
// ---------------------------------------------------------------------------

function ScoreBar({ score, toneClass }: { score: number; toneClass: string }) {
  const pct = Math.max(0, Math.min(SCORE_BAR_MAX, score));
  const thresholdPct = (SCORE_THRESHOLD / SCORE_BAR_MAX) * 100;

  return (
    <div className="atlas-f7-score-bar-wrap" aria-label={`Score ${score} out of 100`}>
      <div className="atlas-f7-score-bar-track">
        <div
          className={cn('atlas-f7-score-bar-fill', toneClass)}
          style={{ width: `${pct}%` }}
          data-testid="f7-score-bar-fill"
        />
        {/* Amber threshold line at 80 */}
        <div
          aria-hidden="true"
          className="atlas-f7-score-bar-threshold"
          style={{ left: `${thresholdPct}%` }}
        />
      </div>
      <div className="atlas-f7-score-bar-labels">
        <span>0</span>
        <span className="atlas-f7-threshold-label">80</span>
        <span>100</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Countdown bar
// ---------------------------------------------------------------------------

function CountdownBar({
  gateCloseDate,
  earningsDate,
  daysToEarnings,
}: {
  gateCloseDate: string;
  earningsDate: string;
  daysToEarnings: number | null;
}) {
  const today = new Date();
  const gateMs = new Date(gateCloseDate).getTime();
  const earningsMs = new Date(earningsDate).getTime();
  const totalMs = earningsMs - gateMs;

  const elapsed = totalMs > 0 ? Math.min(today.getTime() - gateMs, totalMs) : 0;
  const progressPct = totalMs > 0 ? Math.max(0, (elapsed / totalMs) * 100) : 0;

  return (
    <div className="atlas-f7-countdown-wrap">
      <div className="atlas-f7-countdown-bar-track">
        <div
          className="atlas-f7-countdown-bar-fill"
          style={{ width: `${progressPct}%` }}
          data-testid="f7-countdown-fill"
        />
      </div>
      <div className="atlas-f7-countdown-labels">
        <span>Gate {gateCloseDate}</span>
        {daysToEarnings !== null && (
          <span className="atlas-f7-countdown-center">
            {daysToEarnings > 0 ? `${daysToEarnings}d to earnings` : 'Earnings today'}
          </span>
        )}
        <span>Earnings {earningsDate}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rule explanation
// ---------------------------------------------------------------------------

function RuleExplanation({ data, toneClass }: { data: EarningsGate; toneClass: string }) {
  return (
    <>
      <div className={cn('atlas-f7-rule-box', toneClass)}>
        <p className="atlas-f7-rule-text">{data.message}</p>
      </div>

      {data.status === 'DOUBLE BLOCKED' && (
        <div className="atlas-f7-rule-box is-f7-purple atlas-f7-f8-box">
          <p className="atlas-f7-rule-text">
            <strong>Framework 8 also active.</strong> Insider selling detected within the last 30
            days. No adds under any condition — even if the conviction score crosses 80.
          </p>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// 50% CAP deployment boxes
// ---------------------------------------------------------------------------

function CapDeploymentBoxes() {
  return (
    <div className="atlas-f7-cap-boxes">
      <div className="atlas-f7-cap-box">
        <span className="atlas-f7-cap-box-label">Max deployable now</span>
        <span className="atlas-f7-cap-box-value is-f7-amber">50%</span>
        <span className="atlas-f7-cap-box-sub">of target weight</span>
      </div>
      <div className="atlas-f7-cap-box">
        <span className="atlas-f7-cap-box-label">After earnings print</span>
        <span className="atlas-f7-cap-box-value is-f7-green">100%</span>
        <span className="atlas-f7-cap-box-sub">gate reopens</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Post-earnings sequence
// ---------------------------------------------------------------------------

function PostEarningsSequence() {
  return (
    <div className="atlas-f7-sequence" aria-label="Post-earnings sequence" role="list">
      {POST_EARNINGS_STEPS.map((step, i) => (
        <div className="atlas-f7-sequence-item" key={step} role="listitem">
          <span className="atlas-f7-sequence-step">{step}</span>
          {i < POST_EARNINGS_STEPS.length - 1 && (
            <span aria-hidden="true" className="atlas-f7-sequence-arrow">
              →
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
