'use client';

import type { GeopoliticalState } from '@/lib/schemas/regime-modifier';
import { useGeopoliticalStore } from '@/lib/stores/geopolitical-store';
import { cn } from '@/lib/utils';

const OPTIONS: ReadonlyArray<{ label: string; value: GeopoliticalState }> = [
  { label: 'None', value: 'NONE' },
  { label: 'Resolved', value: 'RESOLVED' },
  { label: 'De-escalating', value: 'DE_ESCALATING' },
  { label: 'Active risk', value: 'ACTIVE_RISK' },
  { label: 'Escalating', value: 'ESCALATING' },
];

export function GeopoliticalGateCard() {
  const geopoliticalState = useGeopoliticalStore((s) => s.geopoliticalState);
  const setGeopoliticalState = useGeopoliticalStore((s) => s.setGeopoliticalState);

  return (
    <section className="atlas-briefing-block" data-testid="briefing-geopolitical-gate">
      <h2 className="atlas-briefing-question">Framework 2 Geopolitical Gate</h2>
      <p className="atlas-briefing-callout">
        Brent and VIX stay fully automatic. This five-state flag is the only manual input and
        carries forward from the prior briefing until you change it.
      </p>
      <div className="atlas-briefing-geopolitical-toggle" role="group" aria-label="Geopolitical state">
        {OPTIONS.map((option) => {
          const isActive = geopoliticalState === option.value;
          return (
            <button
              key={option.value}
              aria-pressed={isActive}
              className={cn('atlas-briefing-geopolitical-option', isActive && 'is-active')}
              type="button"
              onClick={() => setGeopoliticalState(option.value)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </section>
  );
}
