import type {
  PortfolioAction,
  PortfolioHoldingSection,
  PortfolioNavItem,
  PortfolioSummaryRow,
} from './portfolio';

export type FrameworkTone = 'default' | 'green' | 'yellow' | 'red' | 'cyan' | 'orange';

export type FrameworkOverviewCard = {
  detail: string;
  label: string;
  options?: readonly string[];
  selectedValue?: string;
  tone: Exclude<FrameworkTone, 'default'>;
  value: string;
};

export type FrameworkCard = {
  rule: string;
  status: string;
  statusTone: FrameworkTone;
  summary: string;
  title: string;
};

export type FrameworkScenarioCard = {
  action: string;
  probability: string;
  summary: string;
  title: string;
  tone: Exclude<FrameworkTone, 'default'>;
};

export type FrameworkSignalRow = {
  label: string;
  tone: FrameworkTone;
  value: string;
};

export type FrameworksScreenData = {
  actions: readonly PortfolioAction[];
  actionsTitle: string;
  appTitle: string;
  frameworks: readonly FrameworkCard[];
  heroSubtitle: string;
  heroTitle: string;
  holdingsSections: readonly PortfolioHoldingSection[];
  logoutLabel: string;
  navItems: readonly PortfolioNavItem[];
  overviewCards: readonly FrameworkOverviewCard[];
  scenarioCards: readonly FrameworkScenarioCard[];
  scenarioTitle: string;
  signalRows: readonly FrameworkSignalRow[];
  signalsTitle: string;
  summaryRows: readonly PortfolioSummaryRow[];
  summaryTitle: string;
};
