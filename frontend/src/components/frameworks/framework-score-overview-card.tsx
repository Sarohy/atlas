'use client';

import { cn } from '@/lib/utils';
import { useFrameworkStore } from '@/lib/stores/framework-store';
import { useExtensionOverlay } from '@/lib/hooks/use-extension-overlay';
import { useExtensionWashout } from '@/lib/hooks/use-extension-washout';
import { useFrameworkScore } from '@/lib/hooks/use-framework-score';
import { useOptionsFlow } from '@/lib/hooks/use-options-flow';
import type { ExtensionOverlayResponse } from '@/lib/schemas/extension-overlay';
import type { ExtensionWashoutResponse } from '@/lib/schemas/extension-washout';
import type { FactorBreakdown, FrameworkScoreResponse } from '@/lib/schemas/framework-score';
import type { OptionsFlowResponse } from '@/lib/schemas/options-flow';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ACTION_TONE_CLASS: Record<string, string> = {
  'tone-green': 'is-green',
  'tone-teal': 'is-teal',
  'tone-blue': 'is-blue',
  'tone-cyan': 'is-cyan',
  'tone-yellow': 'is-yellow',
  'tone-orange': 'is-orange',
  'tone-red': 'is-red',
  'tone-dark-red': 'is-red',
};

const GRADE_TONE: Record<string, string> = {
  'STRONG BUY': 'is-green',
  BUY: 'is-cyan',
  NEUTRAL: 'is-yellow',
  WEAK: 'is-orange',
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * Compact overview card showing the live Framework Score for the currently
 * selected ticker. Sits alongside the VIX Regime, Oil Map, Geopolitical and
 * Capitulation cards in the `.atlas-frameworks-overview` grid.
 *
 * Reads the active ticker from the shared Zustand store so it always reflects
 * whatever the user has selected in the FrameworksPanelsSection below.
 */
export function FrameworkScoreOverviewCard() {
  const activeTicker = useFrameworkStore((s) => s.activeTicker);
  const { data: rawData, isLoading, isError } = useFrameworkScore(activeTicker);
  const { data: rawOptionsFlowData } = useOptionsFlow(activeTicker);
  const { data: rawExtensionOverlayData } = useExtensionOverlay(
    activeTicker,
    rawData?.final_score ?? null,
    rawOptionsFlowData?.f4_score ?? null,
  );
  const { data: rawExtensionWashoutData } = useExtensionWashout(activeTicker);

  const tickerMatch = activeTicker.trim().toUpperCase();
  const matchesActive = <T extends { ticker: string } | undefined | null>(
    payload: T,
  ): T | undefined =>
    payload && payload.ticker.toUpperCase() === tickerMatch ? payload : undefined;

  const data = matchesActive(rawData);
  const optionsFlowData = matchesActive(rawOptionsFlowData);
  const extensionOverlayData = matchesActive(rawExtensionOverlayData);
  const extensionWashoutData = matchesActive(rawExtensionWashoutData);

  const toneCss = data ? (ACTION_TONE_CLASS[data.action_tone] ?? 'is-yellow') : 'is-cyan';

  return (
    <article
      className={cn('atlas-frameworks-overview-card atlas-fws-ov-card', toneCss)}
      data-testid="fws-overview-card"
    >
      <div className="atlas-fws-ov-header">
        <p className="atlas-fws-ov-f1-badge">F1</p>
        <p className="atlas-frameworks-overview-label">Momentum</p>
      </div>

      {isLoading && <p className="atlas-fws-ov-placeholder">Computing…</p>}
      {isError && (
        <p className="atlas-fws-ov-placeholder atlas-fws-ov-placeholder--error">Unavailable</p>
      )}
      {!isLoading && !isError && !data && (
        <p className="atlas-fws-ov-placeholder">Select a ticker</p>
      )}
      {!isLoading && !isError && data && (
        <OverviewCardContent
          data={data}
          optionsFlowData={optionsFlowData}
          extensionOverlayData={extensionOverlayData}
          extensionWashoutData={extensionWashoutData}
        />
      )}
    </article>
  );
}

// ---------------------------------------------------------------------------
// Content — rendered once data is available
// ---------------------------------------------------------------------------

function OverviewCardContent({
  data,
  optionsFlowData,
  extensionOverlayData,
  extensionWashoutData,
}: {
  data: FrameworkScoreResponse;
  optionsFlowData?: OptionsFlowResponse;
  extensionOverlayData?: ExtensionOverlayResponse;
  extensionWashoutData?: ExtensionWashoutResponse;
}) {
  const headlineAction = deriveHeadlineAction(
    data.final_score,
    data,
    optionsFlowData,
    extensionOverlayData,
    extensionWashoutData,
  );
  const actionToneCss = ACTION_TONE_CLASS[headlineAction.tone] ?? 'is-yellow';
  const f1 = data.factors.find((f) => f.key === 'f1');
  const f1Tone = f1 ? (GRADE_TONE[f1.grade] ?? 'is-red') : 'is-yellow';
  const otherFactors = data.factors.filter((f) => f.key !== 'f1');

  return (
    <>
      {/* F1 hero — large and prominent */}
      <div className="atlas-fws-ov-f1-hero">
        <span className={cn('atlas-fws-ov-f1-score', f1Tone)}>{f1?.score ?? '—'}</span>
        <span className="atlas-fws-ov-score-denom"> / 100</span>
        {f1 && (
          <span className={cn('atlas-frameworks-pill atlas-fws-ov-action-pill', f1Tone)}>
            {f1.grade}
          </span>
        )}
      </div>

      {/* Overall conviction + other factors */}
      <div className="atlas-fws-ov-pills">
        <span className={cn('atlas-frameworks-pill atlas-fws-ov-action-pill', actionToneCss)}>
          {headlineAction.label}
        </span>
        {data.f5_blocked && (
          <span className="atlas-frameworks-pill is-red atlas-fws-ov-block-pill">F5 BLOCK</span>
        )}
      </div>

      <div className="atlas-fws-ov-factors">
        {otherFactors.map((f) => (
          <FactorBadge key={f.key} factor={f} />
        ))}
      </div>

      <p className="atlas-frameworks-overview-detail">
        {data.ticker} · score {data.final_score}
      </p>
    </>
  );
}

const ACTION_T1_ELITE_MIN = 85;
const ACTION_T1_MIN = 80;
const ACTION_TIER2_MIN = 70;
const ACTION_TIER3_MIN = 50;

function mapAction(finalScore: number): [string, string] {
  if (finalScore >= ACTION_T1_ELITE_MIN) {
    return ['T1 ELITE — LEAPS ELIGIBLE', 'tone-green'];
  }
  if (finalScore >= ACTION_T1_MIN) {
    return ['T1 CORE', 'tone-teal'];
  }
  if (finalScore >= ACTION_TIER2_MIN) {
    return ['GTC ADDS PERMITTED', 'tone-blue'];
  }
  if (finalScore >= ACTION_TIER3_MIN) {
    return ['SMALL POSITION ONLY', 'tone-yellow'];
  }
  return ['BELOW GATE', 'tone-red'];
}

function hasMajorFlowGap(
  data: FrameworkScoreResponse,
  extensionOverlayData?: ExtensionOverlayResponse,
  extensionWashoutData?: ExtensionWashoutResponse,
): boolean {
  return (
    Boolean(data.f4_data_gap_badge) ||
    (extensionOverlayData?.data_gaps.length ?? 0) > 0 ||
    (extensionWashoutData?.data_gaps.length ?? 0) > 0
  );
}

function hasFlowConfirmation(optionsFlowData?: OptionsFlowResponse): boolean {
  if (!optionsFlowData) {
    return false;
  }
  const action = optionsFlowData.flow_monitor_action;
  return (
    optionsFlowData.f4_score >= 60 && (action === 'ADD_ELIGIBLE' || action === 'ADD_PENDING_GATES')
  );
}

function hasEliteExtensionBlock(
  extensionOverlayData?: ExtensionOverlayResponse,
  extensionWashoutData?: ExtensionWashoutResponse,
): boolean {
  if (extensionOverlayData?.action && extensionOverlayData.action !== 'ADD') {
    return true;
  }
  return Boolean(extensionWashoutData?.negative_catalyst);
}

function hasExtensionBlock(
  extensionOverlayData?: ExtensionOverlayResponse,
  extensionWashoutData?: ExtensionWashoutResponse,
): boolean {
  if (extensionOverlayData?.action && extensionOverlayData.action !== 'ADD') {
    return true;
  }
  return Boolean(extensionWashoutData?.negative_catalyst);
}

function deriveHeadlineAction(
  finalScore: number,
  data: FrameworkScoreResponse,
  optionsFlowData?: OptionsFlowResponse,
  extensionOverlayData?: ExtensionOverlayResponse,
  extensionWashoutData?: ExtensionWashoutResponse,
): { label: string; tone: string } {
  if (data.f5_blocked) {
    const flowAction = optionsFlowData?.flow_monitor_action;
    const flowDeteriorating =
      flowAction === 'TRIM_WATCH' ||
      flowAction === 'AVOID' ||
      (optionsFlowData?.f4_score ?? 100) < 45;

    if (flowDeteriorating) {
      return {
        label: 'TRIM / REDUCE',
        tone: 'tone-red',
      };
    }

    if (finalScore >= ACTION_TIER3_MIN) {
      return {
        label: 'HOLD / WATCH - F5 HARD BLOCK / NO NEW CAPITAL',
        tone: 'tone-yellow',
      };
    }

    return {
      label: 'AVOID / NO NEW CAPITAL',
      tone: 'tone-red',
    };
  }

  if (
    finalScore >= ACTION_T1_ELITE_MIN &&
    hasEliteExtensionBlock(extensionOverlayData, extensionWashoutData)
  ) {
    return {
      label: 'T1 ELITE / CORE HOLD - LEAPS ONLY ON RESET',
      tone: 'tone-yellow',
    };
  }

  if (
    finalScore >= ACTION_TIER2_MIN &&
    hasExtensionBlock(extensionOverlayData, extensionWashoutData)
  ) {
    return {
      label: 'HOLD / WATCH - EXTENSION BLOCK / NO FRESH ADD',
      tone: 'tone-yellow',
    };
  }

  if (
    finalScore >= ACTION_TIER2_MIN &&
    (!hasFlowConfirmation(optionsFlowData) ||
      hasMajorFlowGap(data, extensionOverlayData, extensionWashoutData))
  ) {
    return {
      label: 'WATCH / STARTER ONLY - FLOW CONFIRMATION REQUIRED',
      tone: 'tone-yellow',
    };
  }

  const [label, tone] = mapAction(finalScore);
  return { label, tone };
}

// ---------------------------------------------------------------------------
// Factor badge
// ---------------------------------------------------------------------------

function FactorBadge({ factor }: { factor: FactorBreakdown }) {
  const gradeTone = GRADE_TONE[factor.grade] ?? 'is-red';

  return (
    <span className={cn('atlas-fws-ov-factor', gradeTone)}>
      <span className="atlas-fws-ov-factor-key">{factor.key.toUpperCase()}</span>
      <span className="atlas-fws-ov-factor-score">{factor.score}</span>
    </span>
  );
}
