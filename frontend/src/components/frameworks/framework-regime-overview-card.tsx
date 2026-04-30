'use client';

import { useTickers } from '@/lib/hooks/use-tickers';
import { useRegimeModifier } from '@/lib/hooks/use-regime-modifier';
import { useFrameworkStore } from '@/lib/stores/framework-store';
import { useGeopoliticalStore } from '@/lib/stores/geopolitical-store';
import { cn } from '@/lib/utils';

const REGIME_TONE: Record<string, string> = {
  CLEAR: 'is-green',
  CAUTION: 'is-yellow',
  'SOFT CAUTION': 'is-yellow',
  CRISIS: 'is-red',
  NORMAL: 'is-cyan',
};

export function FrameworkRegimeOverviewCard() {
  const activeTicker = useFrameworkStore((s) => s.activeTicker);
  const { data: tickers } = useTickers();
  const fallbackTicker = tickers?.[0]?.ticker ?? '';
  const ticker = activeTicker.trim().length > 0 ? activeTicker : fallbackTicker;
  const geopoliticalState = useGeopoliticalStore((s) => s.geopoliticalState);
  const { data, isLoading, isError } = useRegimeModifier(ticker, geopoliticalState);

  const regimeValue = data?.effective_regime;
  // Query is disabled until baseScore is cached — treat missing data as pending.
  const isPending = isLoading || (!isError && !regimeValue);
  const toneClass = regimeValue ? (REGIME_TONE[regimeValue] ?? 'is-yellow') : 'is-yellow';

  return (
    <article className={cn('atlas-frameworks-overview-card', 'atlas-frameworks-overview-card--centered', toneClass)}>
      {isPending && (
        <p
          className={cn('atlas-frameworks-overview-value', 'is-yellow')}
          data-testid="framework-regime-overview-value"
        >
          Loading...
        </p>
      )}

      {!isPending && isError && (
        <p
          className={cn('atlas-frameworks-overview-value', 'is-red')}
          data-testid="framework-regime-overview-value"
        >
          Unavailable
        </p>
      )}

      {!isPending && !isError && regimeValue && (
        <p
          className={cn('atlas-frameworks-overview-value', toneClass)}
          data-testid="framework-regime-overview-value"
        >
          {regimeValue}
        </p>
      )}
    </article>
  );
}
