import {
  loadActionsRail,
  loadAtlasShell,
  loadHoldingsSections,
  loadSummaryPanel,
} from './atlas-shell';
import type {
  FrameworkCard,
  FrameworkOverviewCard,
  FrameworkScenarioCard,
  FrameworkSignalRow,
  FrameworksScreenData,
} from '@/types/frameworks';

const HERO_TITLE = 'Frameworks';
const HERO_SUBTITLE =
  'Rulebook status across regime, oil, concentration, and geopolitical gates. Each block is isolated so we can hydrate from one endpoint or many.';
const SCENARIO_TITLE = 'Scenario Router';
const SIGNALS_TITLE = 'Live Diplomatic Signals';

const OVERVIEW_CARDS: readonly FrameworkOverviewCard[] = [
  {
    detail: '',
    label: 'Initial Catalyst',
    options: ['Yes', 'No'],
    selectedValue: 'No',
    tone: 'yellow',
    value: 'No',
  },
  {
    detail: 'Brent $97 · spiking today +5%',
    label: 'Oil Map',
    tone: 'orange',
    value: 'YLW/ORNG',
  },
  {
    detail: 'Saturday deadline · 36 hours',
    label: 'Geopolitical',
    tone: 'red',
    value: 'IRAN DAY 27',
  },
  {
    detail: 'Near green light',
    label: 'Capitulation',
    tone: 'cyan',
    value: '3 / 5',
  },
] as const;

const FRAMEWORK_CARDS: readonly FrameworkCard[] = [
  {
    rule: 'Rule: >30 halt all · 20-30 caution only · <20 normal deploy',
    status: 'CAUTION',
    statusTone: 'yellow',
    summary:
      'VIX declining from 30+ peak. Below 20 = full green light. Currently 25.33 and trending down.',
    title: '#1 VIX Regime Gate',
  },
  {
    rule: 'Rule: 2 consecutive closes above 200-DMA = Phase 2 unlocked',
    status: 'NEAR',
    statusTone: 'yellow',
    summary: 'S&P 6,592 vs 200-DMA 6,630. Two consecutive closes above unlocks Phase 2.',
    title: '#2 200-Day Moving Average',
  },
  {
    rule: 'Rule: <$80 deploy · $80-95 caution · $95-108 pause · >$108 halt',
    status: 'YLW/ORNG',
    statusTone: 'orange',
    summary:
      'Brent $97. Spiking today on Saturday fears. Any buy requires Brent below $100 and declining.',
    title: '#3 Oil Scenario Map',
  },
  {
    rule: 'Rule: <$95 + declining = normal · >$95 = catalyst-only mode',
    status: 'CATALYST-ONLY',
    statusTone: 'yellow',
    summary:
      'Oil at boundary. Saturday binary determines mode reset. Iran deal = immediate normal deploy.',
    title: '#7 Oil Router',
  },
  {
    rule: 'Rule: full flag if 2 hyperscalers confirm HBM compression = exit MU regardless of price',
    status: 'MU PARTIAL',
    statusTone: 'red',
    summary:
      'TurboQuant hits KV cache inference only. HBM training demand untouched. Monitor for second hyperscaler announcement.',
    title: '#8 Thesis Integrity',
  },
  {
    rule: 'Rule: hard cap 15% single name · score capped 85 above 8% · trim on first bounce',
    status: 'MU AT 15%',
    statusTone: 'red',
    summary:
      'MU at 15.0% ceiling. No adds. GTC sell 10-15% at $412 reduces to 12-13%. ~$286-430K proceeds.',
    title: '#13 Concentration Gate',
  },
  {
    rule: 'Rule: active war = caution minimum · confirmed ceasefire = Phase 2 within 30 minutes',
    status: 'IRAN ACTIVE',
    statusTone: 'red',
    summary:
      'Day 27. 15-pt plan rejected. Saturday deadline. US threatening final blow. FM immunity granted.',
    title: '#17 Geopolitical Monitor',
  },
  {
    rule: 'Rule: NVDA -4% intraday = all buy orders cancelled that day',
    status: 'ARMED',
    statusTone: 'yellow',
    summary:
      'NVDA drops more than 4% intraday = cancel all GTC buys for the session. Reset next morning.',
    title: '#19 NVDA Kill Switch',
  },
  {
    rule: 'Rule: 25% = no new optics names · 30% = sell weakest link',
    status: 'OPTICS 26.6%',
    statusTone: 'red',
    summary: 'COHR + CIEN + LITE + MRVL + CRDO = 26.6%. Warning 25% breached. Hard gate 30%.',
    title: '#23 Cluster Gate',
  },
  {
    rule: 'Rule: Day 30+ without resolution = full portfolio re-evaluation',
    status: 'DAY 27',
    statusTone: 'yellow',
    summary:
      'Day 27 in 15-30 tier. Historical: most ME conflicts stabilize within 30 days. Saturday is Day 28.',
    title: '#28 War Duration Ladder',
  },
  {
    rule: 'Rule: 3/5 = Phase 1 · 4/5 = Phase 1+2 · 5/5 = full aggressive deploy',
    status: '3 / 5',
    statusTone: 'yellow',
    summary:
      'Fired: VIX declining, oil below 7-DMA, S&P futures positive. Pending: 200-DMA closes, put/call ratio.',
    title: '#29 Capitulation Signal',
  },
  {
    rule: 'Rule: sources diverge >0.5% = block all orders until reconciled',
    status: 'ACTIVE',
    statusTone: 'green',
    summary:
      'Polygon.io + Alpaca dual-source price verification. 0.5% tolerance gate before any execution fires.',
    title: '#31 Data Oracle',
  },
] as const;

const SCENARIO_CARDS: readonly FrameworkScenarioCard[] = [
  {
    action: 'Deploy $1.5-2M Phase 1+2 immediately.',
    probability: '35%',
    summary: 'Islamabad confirmed. Hormuz partial opening. Oil -15%. S&P +3-5%.',
    title: 'DEAL / EXTENSION',
    tone: 'green',
  },
  {
    action: 'Hold limits. Wait for next binary.',
    probability: '40%',
    summary: 'Another extension. Oil $90-100. Range-bound market.',
    title: 'STALL / EXTEND',
    tone: 'yellow',
  },
  {
    action: 'Cancel all limits. Protect $2.39M floor.',
    probability: '25%',
    summary: 'Strikes resume. Oil $110-130. S&P -4-8%.',
    title: 'ESCALATION',
    tone: 'red',
  },
] as const;

const SIGNAL_ROWS: readonly FrameworkSignalRow[] = [
  { label: 'War day', tone: 'cyan', value: 'DAY 27' },
  { label: '5-day pause expires', tone: 'red', value: 'SATURDAY — 36 hours' },
  { label: 'US position', tone: 'cyan', value: 'Talks + "final blow" threat' },
  { label: 'Iran FM Araghchi', tone: 'red', value: 'Publicly rejecting · privately reviewing' },
  { label: 'Iran FM immunity', tone: 'green', value: 'GRANTED — talks possible' },
  { label: 'UAE intercepts today', tone: 'red', value: '15 missiles + 11 drones' },
  { label: 'IRGC Navy Commander', tone: 'red', value: 'Tangsiri killed by Israel' },
  { label: 'Pakistan PM', tone: 'green', value: 'Hosting + delivered 15-pt plan' },
  { label: 'Goldman base case', tone: 'cyan', value: 'Hormuz normalizes April · Brent <80 Q3' },
  { label: 'Oil today', tone: 'orange', value: '+5% to $94.80 on deadline fears' },
] as const;

function loadFrameworkHero() {
  return Promise.resolve({
    heroSubtitle: HERO_SUBTITLE,
    heroTitle: HERO_TITLE,
  });
}

function loadOverviewCards(): Promise<readonly FrameworkOverviewCard[]> {
  return Promise.resolve(OVERVIEW_CARDS);
}

function loadFrameworkCards(): Promise<readonly FrameworkCard[]> {
  return Promise.resolve(FRAMEWORK_CARDS);
}

function loadScenarioRouter(): Promise<{
  scenarioCards: readonly FrameworkScenarioCard[];
  scenarioTitle: string;
}> {
  return Promise.resolve({
    scenarioCards: SCENARIO_CARDS,
    scenarioTitle: SCENARIO_TITLE,
  });
}

function loadSignalRows(): Promise<{
  signalRows: readonly FrameworkSignalRow[];
  signalsTitle: string;
}> {
  return Promise.resolve({
    signalRows: SIGNAL_ROWS,
    signalsTitle: SIGNALS_TITLE,
  });
}

export async function loadFrameworksScreenData(): Promise<FrameworksScreenData> {
  const [
    shell,
    holdingsSections,
    actionsRail,
    summaryPanel,
    hero,
    overviewCards,
    frameworks,
    scenarioRouter,
    signals,
  ] = await Promise.all([
    loadAtlasShell('/frameworks'),
    loadHoldingsSections(),
    loadActionsRail(),
    loadSummaryPanel(),
    loadFrameworkHero(),
    loadOverviewCards(),
    loadFrameworkCards(),
    loadScenarioRouter(),
    loadSignalRows(),
  ]);

  return {
    actions: actionsRail.actions,
    actionsTitle: actionsRail.actionsTitle,
    appTitle: shell.appTitle,
    frameworks,
    heroSubtitle: hero.heroSubtitle,
    heroTitle: hero.heroTitle,
    holdingsSections,
    logoutLabel: shell.logoutLabel,
    navItems: shell.navItems,
    overviewCards,
    scenarioCards: scenarioRouter.scenarioCards,
    scenarioTitle: scenarioRouter.scenarioTitle,
    signalRows: signals.signalRows,
    signalsTitle: signals.signalsTitle,
    summaryRows: summaryPanel.summaryRows,
    summaryTitle: summaryPanel.summaryTitle,
  };
}
