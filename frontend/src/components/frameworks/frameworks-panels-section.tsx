'use client';

import { useEffect, useState } from 'react';

import { useTickers } from '@/lib/hooks/use-tickers';

import { F1MomentumPanel } from './f1-momentum-panel';
import { F2EarningsPanel } from './f2-earnings-panel';
import { F3AnalystPanel } from './f3-analyst-panel';
import { F4OptionsPanel } from './f4-options-panel';
import { F5FundamentalPanel } from './f5-fundamental-panel';
import { RegimeGuidancePanel } from './regime-guidance-panel';
import { FrameworkScorePanel } from './framework-score-panel';
import { RegimeModifierPanel } from './regime-modifier-panel';
import { TrancheSizingPanel } from './tranche-sizing-panel';
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

  // Derive a sorted, deduplicated list of portfolio ticker symbols.
  const tickers: string[] = (tickerList ?? []).map((t) => t.ticker).sort();

  const [selectedTicker, setSelectedTicker] = useState<string>(EMPTY_TICKER);
  const [detailsOverlayOpen, setDetailsOverlayOpen] = useState(false);
  const [activeWar, setActiveWar] = useState(false);

  // Prefer the user's explicit selection; fall back to the first portfolio
  // ticker so panels are populated automatically on first load.
  const activeTicker =
    selectedTicker !== EMPTY_TICKER ? selectedTicker : (tickers[0] ?? EMPTY_TICKER);

  // Hoist the Framework 1 score so Framework 3 can consume the same value
  // instead of re-fetching independently (TanStack Query deduplicates the
  // network request — the panel's own hook hits the cache).
  const { data: frameworkScoreData } = useFrameworkScore(activeTicker);
  const frameworkFinalScore = frameworkScoreData?.final_score;

  // Hoist the Framework 2 regime rule so Framework 4 uses the same value
  // the investor is seeing in the regime panel — no second independent fetch
  // (TanStack Query deduplicates: identical key, same cached response).
  const { data: regimeData } = useRegimeModifier(activeTicker, activeWar);
  const regimeRule = regimeData?.rule ?? 'NORMAL';

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
        />

        <RegimeModifierPanel
          ticker={activeTicker}
          activeWar={activeWar}
          onToggleWar={() => setActiveWar((v) => !v)}
        />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <RegimeGuidancePanel ticker={activeTicker} baseScore={frameworkFinalScore} />
        <TrancheSizingPanel ticker={activeTicker} regimeRule={regimeRule} />
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
