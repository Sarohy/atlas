'use client';

import { cn } from '@/lib/utils';
import { useFramework29 } from '@/lib/hooks/use-framework29';
import { confirmSignal4 } from '@/lib/api/framework29';
import type { Framework29Result, SignalStatus } from '@/lib/schemas/framework29';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Signal status chip labels. */
const STATUS_LABEL: Record<SignalStatus, string> = {
  CONFIRMED: 'CONFIRMED',
  NOT_MET: 'NOT MET',
  UNAVAILABLE: 'UNAVAILABLE',
  MANUAL_REQUIRED: 'MANUAL REQUIRED',
};

/** Signal status chip CSS classes. */
const STATUS_CHIP_CLASS: Record<SignalStatus, string> = {
  CONFIRMED: 'is-f29-confirmed',
  NOT_MET: 'is-f29-not-met',
  UNAVAILABLE: 'is-f29-unavailable',
  MANUAL_REQUIRED: 'is-f29-manual',
};

/** Gate chip class based on pass state. */
const GATE_CHIP_CLASS = {
  passed: 'is-f29-gate-passed',
  failed: 'is-f29-gate-failed',
} as const;

/** Human-readable signal names (fallback if backend name is empty). */
const SIGNAL_NAMES: Record<number, string> = {
  1: 'VIX Declining',
  2: 'Put/Call Ratio < 1.2',
  3: 'SPY Above 200-Day SMA',
  4: 'Sector ETF Fund Flow',
  5: 'Brent Below 7-Day SMA',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SignalCard({
  signal,
  onManualConfirm,
}: {
  signal: Framework29Result['signals'][number];
  onManualConfirm: (signalNumber: number) => void;
}) {
  const statusClass = STATUS_CHIP_CLASS[signal.status] ?? '';

  return (
    <div
      className={cn('atlas-f29-signal-card', statusClass)}
      data-testid={`f29-signal-${signal.signal_number}`}
    >
      <div className="atlas-f29-signal-card-header">
        <span className="atlas-f29-signal-number">S{signal.signal_number}</span>
        <span className="atlas-f29-signal-name">
          {signal.signal_name || SIGNAL_NAMES[signal.signal_number] || `Signal ${signal.signal_number}`}
        </span>
        <span className={cn('atlas-f29-signal-chip', statusClass)}>
          {STATUS_LABEL[signal.status]}
        </span>
      </div>
      {signal.data_missing && signal.missing_reason && (
        <p className="atlas-f29-signal-missing">{signal.missing_reason}</p>
      )}
      {signal.status === 'MANUAL_REQUIRED' && (
        <button
          className="atlas-f29-confirm-btn"
          type="button"
          onClick={() => onManualConfirm(signal.signal_number)}
        >
          Mark Confirmed
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

// Framework 29 is portfolio-level — no ticker prop needed.
type Framework29CardProps = Record<string, never>;

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Framework 29 — Capitulation / Re-Entry Signal card.
 *
 * Portfolio-level. Sections:
 *   1. Header + gate chip
 *   2. Gate summary bar (N/5 confirmed)
 *   3. Five signal cards
 *   4. Warning messages (if any)
 *   5. Data age footer
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function Framework29Card(_props: Framework29CardProps) {
  const { data, isLoading, isError, error } = useFramework29();
  const errorMsg =
    error instanceof Error ? error.message : 'Failed to load capitulation signal data.';

  async function handleManualConfirm(signalNumber: number) {
    if (signalNumber !== 4) return; // only Signal 4 supports manual confirmation
    try {
      await confirmSignal4(true, 'manual-ui');
    } catch {
      // Silently log — no toast infrastructure in this component.
      // The hook will refetch on next interval.
    }
  }

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-f29-panel"
      data-testid="framework29-card"
    >
      {/* ── Section 1: Header + gate chip ── */}
      <header className="atlas-f29-header">
        <div className="atlas-f29-header-left">
          <h2 className="atlas-frameworks-panel-title">Framework 29</h2>
          <span className="atlas-fws-subtitle">Capitulation / Re-Entry Signal</span>
        </div>
        {data !== undefined && (
          <span
            className={cn(
              'atlas-f29-gate-chip',
              data.and_gate_passed
                ? GATE_CHIP_CLASS.passed
                : GATE_CHIP_CLASS.failed,
            )}
            data-testid="f29-gate-chip"
          >
            {data.and_gate_passed ? 'AND GATE PASSED' : 'GATE NOT MET'}
          </span>
        )}
      </header>

      <div className="atlas-fws-panel-body">
        {isLoading && (
          <p className="atlas-fws-state-msg" data-testid="f29-loading">
            Loading capitulation signals…
          </p>
        )}

        {isError && (
          <p
            className="atlas-fws-state-msg atlas-fws-state-msg--error"
            data-testid="f29-error"
          >
            {errorMsg}
          </p>
        )}

        {!isLoading && !isError && data !== undefined && (
          <>
            {/* ── Section 2: Gate summary bar ── */}
            <div className="atlas-f29-gate-bar" data-testid="f29-gate-bar">
              <div className="atlas-f29-gate-bar-label">
                <span className="atlas-f29-gate-count" data-testid="f29-gate-count">
                  {data.signals_confirmed} / 5 signals confirmed
                </span>
                {data.signals_unavailable > 0 && (
                  <span className="atlas-f29-unavailable-note">
                    ({data.signals_unavailable} unavailable)
                  </span>
                )}
              </div>
              <div className="atlas-f29-gate-track">
                {[1, 2, 3, 4, 5].map((i) => {
                  const signal = data.signals.find((s) => s.signal_number === i);
                  const seg =
                    signal?.status === 'CONFIRMED'
                      ? 'is-f29-seg-confirmed'
                      : signal?.status === 'UNAVAILABLE'
                        ? 'is-f29-seg-unavailable'
                        : 'is-f29-seg-empty';
                  return (
                    <div
                      key={i}
                      className={cn('atlas-f29-gate-seg', seg)}
                    />
                  );
                })}
              </div>
              <p className="atlas-f29-gate-message" data-testid="f29-gate-message">
                {data.gate_message}
              </p>
            </div>

            {/* ── Section 3: Signal cards ── */}
            <div className="atlas-f29-signals-grid" data-testid="f29-signals">
              {data.signals.map((signal) => (
                <SignalCard
                  key={signal.signal_number}
                  signal={signal}
                  onManualConfirm={handleManualConfirm}
                />
              ))}
            </div>

            {/* ── Section 4: Warning messages ── */}
            {data.warning_messages.length > 0 && (
              <ul className="atlas-f29-warnings" data-testid="f29-warnings">
                {data.warning_messages.map((msg, idx) => (
                  <li key={idx} className="atlas-f29-warning-item">
                    {msg}
                  </li>
                ))}
              </ul>
            )}

            {/* ── Section 5: Data age footer ── */}
            <p className="atlas-f29-footer" data-testid="f29-footer">
              {data.cache_hit ? 'cached' : 'live'} · {data.data_age_minutes.toFixed(0)} min ago
            </p>
          </>
        )}
      </div>
    </section>
  );
}
