import {
  loadActionsRail,
  loadAtlasShell,
  loadHoldingsSections,
  loadSummaryPanel,
} from './atlas-shell';
import type {
  BriefingDeployPlanRow,
  BriefingProFormaRow,
  BriefingQuestionSection,
  BriefingSummaryStat,
  BriefingTriggerRow,
  DailyBriefingScreenData,
} from '@/types/daily-briefing';

const BRIEFING_DATE = 'Morning Briefing — Thursday March 26, 2026';
const BRIEFING_SUBTITLE = 'Regime: CAUTION · Iran Day 27 · Saturday binary 36h away · NAV $23.90M';
const BADGE_LABEL = 'DO NOT BUY TODAY';
const Q2_TITLE = 'Q2 — What should I buy today?';
const Q2_CALLOUT =
  'NOTHING TODAY. Oil +5% to $94.80. Framework #7 catalyst-only mode. Saturday binary in 36 hours. $3.585M cash is the weapon. Deploy after resolution.';
const DEPLOY_PLAN_TITLE = 'Post-Saturday Deploy Plan';

const QUESTION_SECTIONS: readonly BriefingQuestionSection[] = [
  {
    rows: [
      {
        body: 'TurboQuant partial flag. KV cache only, HBM training untouched. GTC sell $412 active. Do not sell at $373.',
        status: 'PARTIAL FLAG',
        statusTone: 'yellow',
        symbol: 'MU',
      },
      {
        body: 'NVIDIA $2B locked. S&P 500 member. CPO thesis intact. Normal pullback from $300 ATH.',
        status: 'HOLD',
        statusTone: 'green',
        symbol: 'COHR',
      },
      {
        body: 'Near ATH. Rosenblatt $900 target. Underweight — add target post-Saturday.',
        status: 'HOLD · ADD',
        statusTone: 'green',
        symbol: 'LITE',
      },
      {
        body: 'Q1 rev +33% YoY. Direct cloud +76%. Strongest thesis in portfolio.',
        status: 'HOLD · STRONG',
        statusTone: 'green',
        symbol: 'CIEN',
      },
      {
        body: 'Down 3%. $4B notes, conversion $183 far-dated. Underweight 4.2%.',
        status: 'UNDERWEIGHT',
        statusTone: 'yellow',
        symbol: 'NBIS',
      },
    ],
    title: 'Q1 — What do I own and is anything broken?',
  },
  {
    rows: [
      {
        body: 'Thesis broken. Sell at market today. ~$360K proceeds rotate to MRVL.',
        status: 'SELL TODAY',
        statusTone: 'red',
        symbol: 'ANET',
      },
      {
        body: 'GTC SELL $412 — wait for bounce. ~$286-430K trim proceeds.',
        status: 'GTC ACTIVE',
        statusTone: 'yellow',
        symbol: 'MU',
      },
    ],
    title: 'Q3 — What should I sell or trim today?',
  },
] as const;

const TRIGGER_ROWS: readonly BriefingTriggerRow[] = [
  {
    body: 'Deploy Phase 1 within 30 min. $1.5-2M off the bench immediately.',
    title: 'Trump confirms Iran talks',
  },
  {
    body: 'Cancel all GTC limits. Framework #3 goes red. Protect $2.39M floor.',
    title: 'Brent breaks $100',
  },
  {
    body: 'GTC $412 is closer. Watch for partial fill.',
    title: 'MU bounces above $390',
  },
  {
    body: 'Kill switch #19. Cancel all GTC buys today.',
    title: 'NVDA drops more than 4% intraday',
  },
] as const;

const PRO_FORMA_ROWS: readonly BriefingProFormaRow[] = [
  {
    action: 'TRIM $412',
    actionTone: 'yellow',
    beta: '2.39',
    cluster: 'Memory',
    symbol: 'MU',
    value: '$2.862M',
    weight: '15.0%',
    weightTone: 'red',
  },
  {
    action: 'HOLD',
    actionTone: 'green',
    beta: '1.15',
    cluster: 'Compute',
    symbol: 'TSM',
    value: '$2.437M',
    weight: '12.8%',
  },
  {
    action: 'HOLD',
    actionTone: 'green',
    beta: '2.02',
    cluster: 'Optics',
    clusterTone: 'red',
    symbol: 'COHR',
    value: '$1.814M',
    weight: '9.5%',
  },
  {
    action: 'HOLD',
    actionTone: 'green',
    beta: '1.39',
    cluster: 'Optics',
    clusterTone: 'red',
    symbol: 'CIEN',
    value: '$1.480M',
    weight: '7.7%',
  },
  {
    action: 'HOLD',
    actionTone: 'green',
    beta: '2.10',
    cluster: 'Power',
    symbol: 'VRT',
    value: '$1.195M',
    weight: '6.3%',
  },
  {
    action: 'ADD TARGET',
    actionTone: 'cyan',
    beta: '1.96',
    cluster: 'Optics',
    clusterTone: 'red',
    symbol: 'LITE',
    value: '$1.052M',
    weight: '5.5%',
  },
  {
    action: 'ADD TARGET',
    actionTone: 'cyan',
    beta: '2.09',
    cluster: 'Cloud',
    symbol: 'NBIS',
    value: '$810K',
    weight: '4.2%',
  },
  {
    action: 'PROTECT',
    actionTone: 'green',
    beta: '0.00',
    cluster: '—',
    symbol: 'CASH',
    value: '$3.585M',
    weight: '15.0%',
    weightTone: 'green',
  },
] as const;

const SUMMARY_STATS: readonly BriefingSummaryStat[] = [
  { label: 'Total NAV', tone: 'default', value: '$23.90M' },
  { label: 'Cash vs floor', tone: 'green', value: '$3.585M vs $2.39M OK' },
  { label: 'Optics cluster', tone: 'red', value: '26.6% WARNING' },
  { label: 'Phase 1 deployable', tone: 'cyan', value: '$1.5-2.05M' },
  { label: 'Phase 2 deployable', tone: 'cyan', value: '$1.9-2.78M' },
] as const;

const DEPLOY_PLAN_ROWS: readonly BriefingDeployPlanRow[] = [
  { entry: '$107-113', phase: 'Phase 1 · Iran deal', size: '$400-500K', symbol: 'NBIS' },
  { entry: '$530-560', phase: 'Phase 1 · score 92', size: '$350-450K', symbol: 'FN' },
  { entry: '$780-825', phase: 'Phase 1 · add existing', size: '$500-700K', symbol: 'LITE+' },
  { entry: '$340-358', phase: 'Phase 2 · post confirm', size: '$350-500K', symbol: 'ETN' },
  { entry: '$125-132', phase: 'Phase 2 · power wave', size: '$350-480K', symbol: 'NVT' },
  { entry: '$158-162', phase: 'Phase 2 · 48V Jensen', size: '$350-480K', symbol: 'VICR' },
] as const;

function loadBriefingHero() {
  return Promise.resolve({
    badgeLabel: BADGE_LABEL,
    badgeTone: 'red' as const,
    briefingDate: BRIEFING_DATE,
    briefingSubtitle: BRIEFING_SUBTITLE,
  });
}

function loadQuestionSections(): Promise<readonly BriefingQuestionSection[]> {
  return Promise.resolve(QUESTION_SECTIONS);
}

function loadQ2Callout() {
  return Promise.resolve({
    q2Callout: Q2_CALLOUT,
    q2Title: Q2_TITLE,
  });
}

function loadTriggerRows(): Promise<readonly BriefingTriggerRow[]> {
  return Promise.resolve(TRIGGER_ROWS);
}

function loadProForma(): Promise<readonly BriefingProFormaRow[]> {
  return Promise.resolve(PRO_FORMA_ROWS);
}

function loadSummaryStats(): Promise<readonly BriefingSummaryStat[]> {
  return Promise.resolve(SUMMARY_STATS);
}

function loadDeployPlan(): Promise<{
  deployPlanRows: readonly BriefingDeployPlanRow[];
  deployPlanTitle: string;
}> {
  return Promise.resolve({
    deployPlanRows: DEPLOY_PLAN_ROWS,
    deployPlanTitle: DEPLOY_PLAN_TITLE,
  });
}

export async function loadDailyBriefingScreenData(): Promise<DailyBriefingScreenData> {
  const [
    shell,
    holdingsSections,
    actionsRail,
    summaryPanel,
    hero,
    questionSections,
    q2Section,
    triggerRows,
    proFormaRows,
    summaryStats,
    deployPlan,
  ] = await Promise.all([
    loadAtlasShell('/daily-briefing'),
    loadHoldingsSections(),
    loadActionsRail(),
    loadSummaryPanel(),
    loadBriefingHero(),
    loadQuestionSections(),
    loadQ2Callout(),
    loadTriggerRows(),
    loadProForma(),
    loadSummaryStats(),
    loadDeployPlan(),
  ]);

  return {
    ...actionsRail,
    ...deployPlan,
    ...hero,
    ...q2Section,
    ...shell,
    ...summaryPanel,
    deployPlanRows: deployPlan.deployPlanRows,
    holdingsSections,
    proFormaRows,
    questionSections,
    summaryStats,
    triggerRows,
  };
}
