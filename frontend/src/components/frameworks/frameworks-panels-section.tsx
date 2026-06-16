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
import { ExtensionOverlayPanel } from './extension-overlay-panel';
import { ExtensionWashoutPanel } from './extension-washout-panel';
import { WashoutReferencePanel } from './washout-reference-panel';
import { ForwardGrowthPanel } from './forward-growth-panel';
import { RegimeModifierPanel } from './regime-modifier-panel';
import { TrancheSizingPanel } from './tranche-sizing-panel';
import { CashFloorPanel } from './cash-floor-panel';
import { ConvictionActionPanel } from './conviction-action-panel';
import { Framework7Card } from './framework7-card';
import { Framework8Card } from './framework8-card';
import { Framework9Card } from './framework9-card';
import { Framework13Card } from './framework13-card';
import { Framework14Card } from './framework14-card';
import { Framework29Card } from './framework29-card';
import { Framework30Card } from './framework30-card';
import { Framework33Card } from './framework33-card';
import { LeapsCard } from './leaps-card';
import { Framework11Card } from './framework11-card';
import { Framework15Card } from './framework15-card';
import { Framework18Card } from './framework18-card';
import { Section16Framework12Card } from './section16-framework12-card';
import { useFrameworkScore } from '@/lib/hooks/use-framework-score';
import { useRegimeModifier } from '@/lib/hooks/use-regime-modifier';
import { useFramework8 } from '@/lib/hooks/use-framework8';

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

  // Live position weight (% NAV) for the washout overlay's §3.1 size gate.
  // Derived from position values; null when unsynced so the gate degrades safely.
  const totalNav = (tickerList ?? []).reduce((sum, t) => sum + (t.position_value ?? 0), 0);
  const activeEntry = (tickerList ?? []).find(
    (t) => t.ticker.toUpperCase() === activeTicker.trim().toUpperCase(),
  );
  const activeWeightPct =
    totalNav > 0 && activeEntry?.position_value != null
      ? (activeEntry.position_value / totalNav) * 100
      : null;

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
  // Reject stale payloads from a previously selected ticker. TanStack Query
  // keeps the previous result mounted during a refetch, so when the user
  // switches dropdown selection the regime hook can briefly return the OLD
  // ticker's data. Pairing that stale ``adjusted_score`` with the new
  // ticker's ``final_score`` produces an impossible delta (e.g. MU's pre 77
  // alongside TSEM's leftover adjusted 65 → −12 modifier, when the maximum
  // by spec is −10). The response payload carries its own ticker; ignore
  // anything that doesn't match the current selection.
  const regimeForActive =
    regimeData && regimeData.ticker.toUpperCase() === activeTicker.trim().toUpperCase()
      ? regimeData
      : null;
  const regimeRule = regimeForActive?.rule ?? 'NORMAL';

  // Warm the TanStack Query cache for F8 (same pattern as useFrameworkScore
  // above) so FrameworkScorePanel's own useFramework8 hook hits the cache
  // instead of issuing a second request.
  useFramework8(activeTicker);

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
        {/* Left column: Framework 1 with Extension & Washout directly beneath it
            (no dead gap — the two columns balance in height). */}
        <div className="atlas-frameworks-side-stack">
          <FrameworkScorePanel
            ticker={activeTicker}
            onPreviewDetails={() => setDetailsOverlayOpen(true)}
          />
          <ExtensionWashoutPanel
            ticker={activeTicker}
            positionWeightPct={activeWeightPct}
            beta={activeEntry?.beta ?? null}
          />
        </div>

        {/* Right column: Extension Overlay on top of Forward Growth. */}
        <div className="atlas-frameworks-side-stack">
          <ExtensionOverlayPanel ticker={activeTicker} atlasScore={f1DisplayScore} />
          <ForwardGrowthPanel ticker={activeTicker} atlasScore={f1DisplayScore} />
        </div>
      </div>

      <div className="atlas-frameworks-secondary-row">
        <WashoutReferencePanel />
      </div>

      <div className="atlas-frameworks-secondary-row">
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
        <TrancheSizingPanel
          ticker={activeTicker}
          regimeRule={regimeRule}
          brentPrice={regimeForActive?.brent_price ?? null}
          brentConsecutiveBelow95Count={regimeForActive?.brent_consecutive_below_95_count ?? 0}
          geopoliticalState={geopoliticalState}
        />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <CashFloorPanel />
        <ConvictionActionPanel ticker={activeTicker} adjustedScore={f1DisplayScore} />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <Framework7Card ticker={activeTicker} adjustedScore={f1DisplayScore} />
        <Framework8Card ticker={activeTicker} />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <Framework9Card ticker={activeTicker} />
        <LeapsCard ticker={activeTicker} score={f1DisplayScore ?? undefined} />
        <Framework11Card />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <Section16Framework12Card ticker={activeTicker} />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <Framework13Card ticker={activeTicker} />
        <Framework14Card ticker={activeTicker} />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <Framework15Card />
        <Framework29Card ticker={activeTicker ?? ''} />
        <Framework30Card />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <Framework18Card />
      </div>

      <div className="atlas-frameworks-secondary-row">
        <Framework33Card ticker={activeTicker} />
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
            <div className="atlas-frameworks-details-row">
              <F3AnalystPanel ticker={activeTicker} />
              <F4OptionsPanel ticker={activeTicker} />
            </div>
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
