'use client';

import { useRegimeModifier } from '@/lib/hooks/use-regime-modifier';
import type { GeopoliticalState } from '@/lib/schemas/regime-modifier';
import { cn } from '@/lib/utils';

type RegimeModifierPanelProps = {
  ticker: string;
  geopoliticalState: GeopoliticalState;
  onGeopoliticalStateChange: (state: GeopoliticalState) => void;
};

export function RegimeModifierPanel({
  ticker,
  geopoliticalState,
  onGeopoliticalStateChange,
}: RegimeModifierPanelProps) {
  const activeTicker = ticker.trim().length > 0;
  const { data: regime, isLoading, isError, error } = useRegimeModifier(ticker, geopoliticalState);
  const errorMsg = error instanceof Error ? error.message : 'Failed to load regime data.';

  return (
    <section
      className="atlas-frameworks-panel atlas-fws-panel atlas-regime-panel"
      data-testid="regime-modifier-panel"
    >
      <header className="atlas-frameworks-panel-header atlas-fws-panel-header">
        <h2 className="atlas-frameworks-panel-title">Framework 2</h2>
        <span className="atlas-fws-subtitle">Brent · VIX · Geopolitical Gate → Regime</span>
      </header>

      <div className="atlas-fws-panel-body">
        <GeopoliticalToggle value={geopoliticalState} onChange={onGeopoliticalStateChange} />
        {isLoading && <LoadingState />}
        {isError && <ErrorState message={errorMsg} />}
        {!isLoading && !isError && regime && (
          <RegimeContent
            brentPrice={regime.brent_price}
            brentStreak={regime.brent_consecutive_below_95_count}
            determinationText={regime.determination_text}
            geopoliticalState={regime.geopolitical_state}
            rule={regime.rule}
            vixValue={regime.vix_value}
            modifier={regime.modifier}
            specialCaseActive={regime.special_case_active ?? false}
          />
        )}
        {!isLoading && !isError && !regime && activeTicker && <EmptyState ticker={ticker} />}
      </div>
    </section>
  );
}

const GEOPOLITICAL_OPTIONS: ReadonlyArray<{
  label: string;
  value: GeopoliticalState;
}> = [
  { label: 'None', value: 'NONE' },
  { label: 'Resolved', value: 'RESOLVED' },
  { label: 'De-escalating', value: 'DE_ESCALATING' },
  { label: 'Active risk', value: 'ACTIVE_RISK' },
  { label: 'Escalating', value: 'ESCALATING' },
];

function GeopoliticalToggle({
  value,
  onChange,
}: {
  value: GeopoliticalState;
  onChange: (state: GeopoliticalState) => void;
}) {
  return (
    <div aria-label="Geopolitical state" className="atlas-regime-geopolitical-toggle" role="group">
      {GEOPOLITICAL_OPTIONS.map((option) => (
        <button
          key={option.value}
          aria-pressed={value === option.value}
          className={cn('atlas-regime-geopolitical-option', value === option.value && 'is-active')}
          type="button"
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function LoadingState() {
  return (
    <p className="atlas-fws-state-msg" data-testid="regime-loading">
      Fetching Brent & VIX...
    </p>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="atlas-fws-state-msg atlas-fws-state-msg--error" data-testid="regime-error">
      {message}
    </p>
  );
}

function EmptyState({ ticker }: { ticker: string }) {
  return (
    <p className="atlas-fws-state-msg" data-testid="regime-empty">
      No data available for {ticker}.
    </p>
  );
}

type RegimeContentProps = {
  brentPrice: number | null;
  brentStreak: number;
  determinationText: string;
  geopoliticalState: GeopoliticalState;
  rule: string;
  vixValue: number | null;
  modifier: number;
  specialCaseActive: boolean;
};

function RegimeContent({
  brentPrice,
  brentStreak,
  determinationText,
  geopoliticalState,
  rule,
  vixValue,
  modifier,
  specialCaseActive,
}: RegimeContentProps) {
  void geopoliticalState;
  void rule;
  void modifier;

  return (
    <div className="atlas-regime-content" data-testid="regime-content">
      <div className="atlas-regime-market-row">
        <RegimeStat
          label="BRENT"
          testId="regime-brent"
          value={brentPrice !== null ? `$${brentPrice.toFixed(2)}` : '-'}
        />
        <div className="atlas-regime-stat-divider" />
        <RegimeStat
          label="VIX"
          testId="regime-vix"
          value={vixValue !== null ? vixValue.toFixed(2) : '-'}
        />
        <div className="atlas-regime-stat-divider" />
        <RegimeStat
          label="BRENT < $95 STREAK"
          testId="regime-brent-streak"
          value={String(brentStreak)}
        />
      </div>

      {specialCaseActive && (
        <div className="atlas-regime-special-case-badge" data-testid="regime-geo-penalty-badge">
          GEO PENALTY ACTIVE
        </div>
      )}

      <div className="atlas-regime-determination" data-testid="regime-determination">
        {determinationText}
      </div>
    </div>
  );
}

function RegimeStat({
  label,
  testId,
  tone,
  value,
}: {
  label: string;
  testId: string;
  tone?: string;
  value: string;
}) {
  return (
    <div className="atlas-regime-stat">
      <span className="atlas-regime-stat-label">{label}</span>
      <span className={cn('atlas-regime-stat-value', tone)} data-testid={testId}>
        {value}
      </span>
    </div>
  );
}
