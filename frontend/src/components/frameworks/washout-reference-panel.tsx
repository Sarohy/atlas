'use client';

import { cn } from '@/lib/utils';
import { useWashoutReference } from '@/lib/hooks/use-washout-reference';
import type { WashoutReferenceResponse } from '@/lib/schemas/washout-reference';

const FLAG_TONE: Record<string, string> = {
  'hard-override': 'is-red',
  provisional: 'is-orange',
  'watch-promote': 'is-yellow',
  'excl-recalibration': 'is-muted',
  'low-confidence': 'is-muted',
};

/**
 * Washout Overlay reference — the Settings thresholds (§10, read-only; editable
 * in config / quarterly recompute) and the per-name Risk exception rows.
 * Reference data only; not per-ticker.
 */
export function WashoutReferencePanel() {
  const { data, isLoading, isError } = useWashoutReference();

  return (
    <section className="atlas-frameworks-panel atlas-fws-panel" data-testid="washout-reference-panel">
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <div>
          <h2 className="atlas-frameworks-panel-title">Washout Overlay — Settings &amp; Risk</h2>
          <span className="atlas-fws-subtitle">Editable thresholds (§10) · per-name exceptions</span>
        </div>
      </header>
      <div className="atlas-fws-panel-body">
        {isLoading && <p className="atlas-fws-state-msg">Loading reference…</p>}
        {isError && <p className="atlas-fws-state-msg atlas-fws-state-msg--error">Failed to load.</p>}
        {data && <ReferenceContent data={data} />}
      </div>
    </section>
  );
}

function ReferenceContent({ data }: { data: WashoutReferenceResponse }) {
  const groups = [...new Set(data.thresholds.map((t) => t.group))];
  return (
    <div data-testid="washout-reference-content">
      {/* Settings thresholds (§10) */}
      <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
        <span className="atlas-fws-calc-label">Settings thresholds (provisional)</span>
        <span className="atlas-fws-calc-value">{data.thresholds.length}</span>
      </div>
      {groups.map((group) => (
        <div key={group}>
          <div className="atlas-fws-breakdown-divider" />
          <p className="atlas-fws-subtitle">{group}</p>
          {data.thresholds
            .filter((t) => t.group === group)
            .map((t) => (
              <div className="atlas-fws-calc-row" key={t.key}>
                <span className="atlas-fws-calc-label">{t.key}</span>
                <span className="atlas-fws-calc-value">{t.value}</span>
              </div>
            ))}
        </div>
      ))}

      {/* Risk exception rows */}
      <div className="atlas-fws-breakdown-divider" />
      <div className="atlas-fws-calc-row atlas-fws-calc-row--total">
        <span className="atlas-fws-calc-label">Risk exceptions</span>
        <span className="atlas-fws-calc-value" data-testid="washout-exception-count">
          {data.exceptions.length}
        </span>
      </div>
      {data.exceptions.map((e) => (
        <div className="atlas-fws-calc-row" key={e.ticker}>
          <span className="atlas-fws-calc-label">
            {e.ticker} · {e.elasticity_tier.replace('_', '-').toLowerCase()}
          </span>
          <span className="atlas-f4-signal-row">
            {e.flags.map((f) => (
              <span
                key={f}
                className={cn('atlas-frameworks-pill atlas-f4-tier-pill', FLAG_TONE[f] ?? 'is-muted')}
              >
                {f}
              </span>
            ))}
          </span>
        </div>
      ))}
    </div>
  );
}
