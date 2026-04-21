'use client';

import { useEffect, useState } from 'react';

import { useTickers } from '@/lib/hooks/use-tickers';
import { useFrameworkStore } from '@/lib/stores/framework-store';
import { useGeopoliticalStore } from '@/lib/stores/geopolitical-store';

import { F1MomentumPanel } from './f1-momentum-panel';
import { F2EarningsPanel } from './f2-earnings-panel';
import { F3AnalystPanel } from './f3-analyst-panel';
import { F4OptionsPanel } from './f4-options-panel';
import { F5FundamentalPanel } from './f5-fundamental-panel';
import { RegimeGuidancePanel } from './regime-guidance-panel';
import { FrameworkScorePanel } from './framework-score-panel';
import { RegimeModifierPanel } from './regime-modifier-panel';
import { TrancheSizingPanel } from './tranche-sizing-panel';
import { CashFloorPanel } from './cash-floor-panel';
import { ConvictionActionPanel } from './conviction-action-panel';
import { Framework7Card } from './framework7-card';
import { Framework8Card } from './framework8-card';
import { Framework14Card } from './framework14-card';
import { useFrameworkScore } from '@/lib/hooks/use-framework-score';
import { useRegimeModifier } from '@/lib/hooks/use-regime-modifier';

// ---------------------------------------------------------------------------
// Named constants
// ---------------------------------------------------------------------------

/** Fallback ticker string when the portfolio is empty or still loading. */
const EMPTY_TICKER = '';

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * FrameworksPanelsSection — one shared ticker select bar followed by all five
 * framework analysis panels (F1–F5). A single selection drives every panel so
 * the user never needs to switch tickers five separate times.
 */
export function FrameworksPanelsSection() {
  const { data: tickerList, isLoading: tickersLoading, isError: tickersError } = useTickers();
  const setActiveTicker = useFrameworkStore((s) => s.setActiveTicker);
  // Read the exact score written by FrameworkScorePanel — this is the value
  // the investor actually sees (re-computed from live factor hooks + regime
  // modifier). Reading it from the store guarantees F6/F7 use an identical
  // number rather than re-deriving from a different data source.
  const f1DisplayScore = useFrameworkStore((s) => s.f1DisplayScore);

  // Derive a sorted, deduplicated list of portfolio ticker symbols.
  const tickers: string[] = (tickerList ?? []).map((t) => t.ticker).sort();

  const [selectedTicker, setSelectedTicker] = useState<string>(EMPTY_TICKER);
  const [detailsOverlayOpen, setDetailsOverlayOpen] = useState(false);
  const geopoliticalState = useGeopoliticalStore((s) => s.geopoliticalState);
  const setGeopoliticalState = useGeopoliticalStore((s) => s.setGeopoliticalState);

  // Prefer the user's explicit selection; fall back to the first portfolio
  // ticker so panels are populated automatically on first load.
  const activeTicker =
    selectedTicker !== EMPTY_TICKER ? selectedTicker : (tickers[0] ?? EMPTY_TICKER);

  // Hoist the Framework 1 score so Framework 3 can consume the same value.
  // We gate F3 on f1DisplayScore (the regime-adjusted score the investor sees)
  // so F3 bands are always evaluated against the exact number shown in F1.
  // The raw frameworkScoreData is still fetched here so FrameworkScorePanel's
  // own hook hits the TanStack Query cache instead of making a second request.
  useFrameworkScore(activeTicker);

  // Hoist the Framework 2 regime rule so Framework 4 uses the same value
  // the investor is seeing in the regime panel — no second independent fetch
  // (TanStack Query deduplicates: identical key, same cached response).
  const { data: regimeData } = useRegimeModifier(activeTicker, geopoliticalState);
  const regimeRule = regimeData?.rule ?? 'NORMAL';

  useEffect(() => {
    setActiveTicker(activeTicker);
  }, [activeTicker, setActiveTicker]);

  useEffect(() => {
    if (!detailsOverlayOpen) {
      return undefined;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setDetailsOverlayOpen(false);
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [detailsOverlayOpen]);

  return (
    <div className="atlas-frameworks-panels-section" data-testid="frameworks-panels-section">
      {/* Shared ticker selection bar — rendered once above all five panels */}
      <div className="atlas-frameworks-ticker-bar" data-testid="frameworks-ticker-bar">
        <span className="atlas-frameworks-ticker-bar-label">Analysing</span>

        {tickersLoading && (
          <span
            className="atlas-frameworks-ticker-bar-state"
            data-testid="frameworks-tickers-loading"
          >
            Loading tickers…
          </span>
        )}

        {tickersError && (
          <span
            className="atlas-frameworks-ticker-bar-state atlas-frameworks-ticker-bar-state--error"
            data-testid="frameworks-tickers-error"
          >
            Failed to load portfolio tickers
          </span>
        )}

        {!tickersLoading && !tickersError && tickers.length > 0 && (
          <FrameworksTickerSelect
            tickers={tickers}
            value={activeTicker}
            onChange={setSelectedTicker}
          />
        )}
      </div>

      <div className="atlas-regime-panels-row">
        <FrameworkScorePanel
          ticker={activeTicker}
          onPreviewDetails={() => setDetailsOverlayOpen(true)}
          regimeModifier={regimeData?.modifier ?? 0}
        />

        <RegimeModifierPanel
          ticker={activeTicker}
          geopoliticalState={geopoliticalState}
          onGeopoliticalStateChange={setGeopoliticalState}
        />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <RegimeGuidancePanel
          ticker={activeTicker}
          baseScore={f1DisplayScore}
          enabled={f1DisplayScore !== undefined}
        />
        <TrancheSizingPanel ticker={activeTicker} regimeRule={regimeRule} />
        <CashFloorPanel ticker={activeTicker} />
        <ConvictionActionPanel ticker={activeTicker} adjustedScore={f1DisplayScore} />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <Framework7Card ticker={activeTicker} adjustedScore={f1DisplayScore} />
        <Framework8Card ticker={activeTicker} />
        <Framework14Card ticker={activeTicker} />
      </div>

      {/* Always mounted so F1-F5 hooks pre-fetch data before the overlay opens.
          Visibility is toggled with CSS (display:none) rather than conditional
          rendering — this prevents the first-hover "no data" flash caused by
          React Query having no cache on fresh mounts. */}
      <div
        aria-hidden={!detailsOverlayOpen}
        aria-label={detailsOverlayOpen ? 'Framework detail cards' : undefined}
        className="atlas-frameworks-details-overlay"
        role={detailsOverlayOpen ? 'dialog' : undefined}
        style={detailsOverlayOpen ? undefined : { display: 'none' }}
        onMouseLeave={() => setDetailsOverlayOpen(false)}
        onClick={(event) => {
          if (event.target === event.currentTarget) {
            setDetailsOverlayOpen(false);
          }
        }}
      >
        <div className="atlas-frameworks-details-dialog">
          <div className="atlas-frameworks-details-header">
            <div>
              <h2 className="atlas-frameworks-details-title">Framework Detail Cards</h2>
              <p className="atlas-frameworks-details-subtitle">
                {activeTicker !== EMPTY_TICKER
                  ? `Showing the current F1-F5 breakdown for ${activeTicker}.`
                  : 'Showing the current F1-F5 breakdown.'}
              </p>
            </div>
            <button
              aria-label="Close framework detail cards"
              className="atlas-frameworks-details-close"
              type="button"
              onClick={() => setDetailsOverlayOpen(false)}
            >
              Close
            </button>
          </div>

          <div className="atlas-frameworks-details-grid">
            <F1MomentumPanel ticker={activeTicker} />
            <F2EarningsPanel ticker={activeTicker} />
            <F3AnalystPanel ticker={activeTicker} />
            <F4OptionsPanel ticker={activeTicker} />
            <F5FundamentalPanel ticker={activeTicker} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared ticker selector
// ---------------------------------------------------------------------------

type FrameworksTickerSelectProps = {
  tickers: readonly string[];
  value: string;
  onChange: (ticker: string) => void;
};

function FrameworksTickerSelect({ tickers, value, onChange }: FrameworksTickerSelectProps) {
  return (
    <select
      className="atlas-frameworks-ticker-select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Select ticker for framework analysis"
      data-testid="frameworks-ticker-select"
    >
      {tickers.map((t) => (
        <option key={t} value={t}>
          {t}
        </option>
      ))}
    </select>
  );
}
