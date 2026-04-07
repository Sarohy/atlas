export type PortfolioAccentTone = 'cyan' | 'green' | 'red' | 'yellow';

export type PortfolioValueTone = 'default' | 'green' | 'red';

export type PortfolioNavItem = {
  href: string;
  isActive: boolean;
  label: string;
};

export type PortfolioMetricCard = {
  detail: string;
  label: string;
  tone: PortfolioAccentTone;
  value: string;
  valueTone?: PortfolioValueTone;
};

export type PortfolioHolding = {
  allocation: string;
  dayChange: string;
  dayChangeTone: PortfolioValueTone;
  progressTone: PortfolioAccentTone;
  progressValue: number;
  symbol: string;
  value: string;
};

export type PortfolioHoldingSection = {
  items: readonly PortfolioHolding[];
  title: string;
};

export type PortfolioTicker = {
  change: string;
  changeTone: PortfolioValueTone;
  label: string;
  price: string;
  symbol: string;
};

export type PortfolioCashPanel = {
  actionLabel: string;
  balanceLabel: string;
  balanceValue: string;
  periodLabel: string;
  title: string;
};

export type PortfolioAction = {
  description: string;
  metadata: string;
  title: string;
  tone: PortfolioAccentTone;
};

export type PortfolioSummaryRow = {
  label: string;
  tone: PortfolioAccentTone | 'default';
  value: string;
};

export type PortfolioScreenData = {
  actions: readonly PortfolioAction[];
  actionsTitle: string;
  appTitle: string;
  cashPanel: PortfolioCashPanel;
  holdingsSections: readonly PortfolioHoldingSection[];
  logoutLabel: string;
  metricCards: readonly PortfolioMetricCard[];
  navItems: readonly PortfolioNavItem[];
  summaryRows: readonly PortfolioSummaryRow[];
  summaryTitle: string;
  tickerEditorLabel: string;
  tickerPanelTitle: string;
  tickers: readonly PortfolioTicker[];
};
