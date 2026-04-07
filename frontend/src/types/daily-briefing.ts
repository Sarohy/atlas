import type {
  PortfolioAction,
  PortfolioHoldingSection,
  PortfolioNavItem,
  PortfolioSummaryRow,
} from './portfolio';

export type BriefingStatusTone = 'default' | 'green' | 'yellow' | 'red' | 'cyan';

export type BriefingCalloutTone = 'green' | 'red';

export type BriefingPositionRow = {
  body: string;
  status: string;
  statusTone: BriefingStatusTone;
  symbol: string;
};

export type BriefingQuestionSection = {
  rows: readonly BriefingPositionRow[];
  title: string;
};

export type BriefingTriggerRow = {
  body: string;
  title: string;
};

export type BriefingProFormaRow = {
  action: string;
  actionTone: BriefingStatusTone;
  beta: string;
  cluster: string;
  clusterTone?: BriefingStatusTone;
  symbol: string;
  value: string;
  weight: string;
  weightTone?: BriefingStatusTone;
};

export type BriefingSummaryStat = {
  label: string;
  tone: BriefingStatusTone;
  value: string;
};

export type BriefingDeployPlanRow = {
  entry: string;
  phase: string;
  size: string;
  symbol: string;
};

export type DailyBriefingScreenData = {
  actions: readonly PortfolioAction[];
  actionsTitle: string;
  appTitle: string;
  badgeLabel: string;
  badgeTone: BriefingCalloutTone;
  briefingDate: string;
  briefingSubtitle: string;
  deployPlanRows: readonly BriefingDeployPlanRow[];
  deployPlanTitle: string;
  holdingsSections: readonly PortfolioHoldingSection[];
  logoutLabel: string;
  navItems: readonly PortfolioNavItem[];
  proFormaRows: readonly BriefingProFormaRow[];
  questionSections: readonly BriefingQuestionSection[];
  q2Callout: string;
  q2Title: string;
  summaryRows: readonly PortfolioSummaryRow[];
  summaryStats: readonly BriefingSummaryStat[];
  summaryTitle: string;
  triggerRows: readonly BriefingTriggerRow[];
};
