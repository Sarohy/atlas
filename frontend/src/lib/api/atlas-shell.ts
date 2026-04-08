import type {
  PortfolioAction,
  PortfolioHoldingSection,
  PortfolioNavItem,
  PortfolioSummaryRow,
  PortfolioScreenData,
} from '@/types/portfolio';

const APP_TITLE = 'ATLAS v7.0';
const LOGOUT_LABEL = 'Logout';

const NAV_ITEMS = [
  { href: '/daily-briefing', label: 'Daily Briefing' },
  { href: '/', label: 'Portfolio' },
  { href: '/frameworks', label: 'Frameworks' },
  { href: '/clusters', label: 'Clusters' },
  { href: '/watchlist', label: 'Watchlist' },
] as const;

const HOLDING_SECTIONS: readonly PortfolioHoldingSection[] = [
  {
    title: 'Holdings — AI Core',
    items: [
      {
        allocation: '15.0% · β2.39',
        dayChange: '-3.4%',
        dayChangeTone: 'red',
        progressTone: 'red',
        progressValue: 95,
        symbol: 'MU',
        value: '$2.862M',
      },
      {
        allocation: '12.8% · β1.15',
        dayChange: '+1.3%',
        dayChangeTone: 'green',
        progressTone: 'cyan',
        progressValue: 85,
        symbol: 'TSM',
        value: '$2.437M',
      },
      {
        allocation: '9.5% · β2.02',
        dayChange: '-1.2%',
        dayChangeTone: 'red',
        progressTone: 'yellow',
        progressValue: 63,
        symbol: 'COHR',
        value: '$1.814M',
      },
      {
        allocation: '7.7% · β1.39',
        dayChange: '+0.8%',
        dayChangeTone: 'green',
        progressTone: 'cyan',
        progressValue: 51,
        symbol: 'CIEN',
        value: '$1.480M',
      },
      {
        allocation: '6.3% · β2.10',
        dayChange: '-0.9%',
        dayChangeTone: 'red',
        progressTone: 'cyan',
        progressValue: 42,
        symbol: 'VRT',
        value: '$1.195M',
      },
      {
        allocation: '5.5% · β1.96',
        dayChange: '+2.1%',
        dayChangeTone: 'green',
        progressTone: 'cyan',
        progressValue: 36,
        symbol: 'LITE',
        value: '$1.052M',
      },
      {
        allocation: '4.2% · β2.09',
        dayChange: '-3.0%',
        dayChangeTone: 'red',
        progressTone: 'yellow',
        progressValue: 28,
        symbol: 'NBIS',
        value: '$810K',
      },
      {
        allocation: '3.4% · β1.35',
        dayChange: '+0.2%',
        dayChangeTone: 'green',
        progressTone: 'cyan',
        progressValue: 23,
        symbol: 'AVGO',
        value: '$657K',
      },
      {
        allocation: '2.9% · β1.75',
        dayChange: '+6.6%',
        dayChangeTone: 'green',
        progressTone: 'cyan',
        progressValue: 19,
        symbol: 'MRVL',
        value: '$561K',
      },
      {
        allocation: '2.1% · β0.65',
        dayChange: '+0.4%',
        dayChangeTone: 'green',
        progressTone: 'green',
        progressValue: 14,
        symbol: 'CEG',
        value: '$401K',
      },
      {
        allocation: '2.1% · β2.74',
        dayChange: '-4.3%',
        dayChangeTone: 'red',
        progressTone: 'red',
        progressValue: 14,
        symbol: 'SNDK',
        value: '$401K',
      },
      {
        allocation: '0.5% · β0.40',
        dayChange: '+1.1%',
        dayChangeTone: 'green',
        progressTone: 'green',
        progressValue: 4,
        symbol: 'NEM',
        value: '$90K',
      },
    ],
  },
  {
    title: 'Cash',
    items: [
      {
        allocation: '15.0% · floor $2.39M',
        dayChange: 'PROTECTED',
        dayChangeTone: 'green',
        progressTone: 'green',
        progressValue: 100,
        symbol: 'CASH',
        value: '$3.585M',
      },
    ],
  },
] as const;

const ACTIONS_TITLE = "Today's Actions";
const ACTIONS: readonly PortfolioAction[] = [
  {
    description: '$3.585M sitting ready. Saturday binary 36h away. No deploys.',
    metadata: 'FRAMEWORK #7 · #17',
    title: 'HOLD CASH',
    tone: 'cyan',
  },
  {
    description: 'at market today. Thesis broken. ~$360K proceeds -> MRVL.',
    metadata: 'SCORE 62 · THESIS BROKEN',
    title: 'SELL ANET',
    tone: 'red',
  },
  {
    description: '$412 active. 10-15% trim = $286-430K proceeds when it bounces.',
    metadata: 'FRAMEWORK #13 · TURBOQUANT',
    title: 'MU GTC SELL',
    tone: 'yellow',
  },
  {
    description: 'lowered to $107-110. $400-500K ready to deploy post-Saturday.',
    metadata: 'SCORE 91 · UNDERWEIGHT 4.2%',
    title: 'NBIS limit',
    tone: 'cyan',
  },
  {
    description: '$530-560. Score 92. $350-450K. Satellite #1. Zero dilution.',
    metadata: 'SCORE 92 · β 0.96',
    title: 'FN GTC',
    tone: 'cyan',
  },
] as const;

const SUMMARY_TITLE = 'Portfolio Summary';
const SUMMARY_ROWS: readonly PortfolioSummaryRow[] = [
  { label: 'Total NAV', tone: 'cyan', value: '$23.90M' },
  { label: 'Invested', tone: 'default', value: '$20.315M (85%)' },
  { label: 'Cash', tone: 'green', value: '$3.585M (15%)' },
  { label: 'Cash floor', tone: 'green', value: '$2.39M (10%)' },
  { label: 'Deployable', tone: 'cyan', value: '$1.195M above floor' },
  { label: 'Phase 1 ready', tone: 'cyan', value: '$1.5–2.05M' },
  { label: 'Phase 2 ready', tone: 'cyan', value: '$1.9–2.78M' },
  { label: 'Optic cluster', tone: 'red', value: '26.6% !' },
  { label: 'Beta', tone: 'default', value: '1.09 total · 1.40 invested' },
] as const;

function buildNavItems(activeHref: string): readonly PortfolioNavItem[] {
  return NAV_ITEMS.map((item) => ({
    href: item.href,
    isActive: item.href === activeHref,
    label: item.label,
  }));
}

export function loadAtlasShell(
  activeHref: string,
): Promise<Pick<PortfolioScreenData, 'appTitle' | 'logoutLabel' | 'navItems'>> {
  return Promise.resolve({
    appTitle: APP_TITLE,
    logoutLabel: LOGOUT_LABEL,
    navItems: buildNavItems(activeHref),
  });
}

export function loadHoldingsSections(): Promise<readonly PortfolioHoldingSection[]> {
  return Promise.resolve(HOLDING_SECTIONS);
}

export function loadActionsRail(): Promise<{
  actions: readonly PortfolioAction[];
  actionsTitle: string;
}> {
  return Promise.resolve({
    actions: ACTIONS,
    actionsTitle: ACTIONS_TITLE,
  });
}

export function loadSummaryPanel(): Promise<{
  summaryRows: readonly PortfolioSummaryRow[];
  summaryTitle: string;
}> {
  return Promise.resolve({
    summaryRows: SUMMARY_ROWS,
    summaryTitle: SUMMARY_TITLE,
  });
}
