import {
  loadActionsRail,
  loadAtlasShell,
  loadHoldingsSections,
  loadSummaryPanel,
} from './atlas-shell';
import type {
  PortfolioCashPanel,
  PortfolioScreenData,
  PortfolioTicker,
  PortfolioMetricCard,
} from '@/types/portfolio';
const TICKER_PANEL_TITLE = 'All Tickers';
const TICKER_EDITOR_LABEL = 'Edit Tickers';

const METRIC_CARDS: readonly PortfolioMetricCard[] = [
  {
    detail: '↓ $420K today',
    label: 'Total Portfolio',
    tone: 'cyan',
    value: '$23.90M',
  },
  {
    detail: '15.0% · floor $2.39M',
    label: 'Cash Reserve',
    tone: 'green',
    value: '$3.585M',
    valueTone: 'green',
  },
  {
    detail: 'incl. cash · 1.40 invested',
    label: 'Portfolio Beta',
    tone: 'yellow',
    value: '1.09',
  },
  {
    detail: 'above 25% warning',
    label: 'Optics Cluster',
    tone: 'red',
    value: '26.6%',
    valueTone: 'red',
  },
] as const;

const TICKERS: readonly PortfolioTicker[] = [
  {
    change: '11%',
    changeTone: 'green',
    label: 'Apple, Inc',
    price: '$4,008.65',
    symbol: 'AAPL',
  },
  {
    change: '11%',
    changeTone: 'green',
    label: 'Spotify.com',
    price: '$4,008.65',
    symbol: 'SPOT',
  },
  {
    change: '11%',
    changeTone: 'green',
    label: 'Airbnb, Inc',
    price: '$4,008.65',
    symbol: 'ABNB',
  },
  {
    change: '11%',
    changeTone: 'green',
    label: 'Spotify.com',
    price: '$4,008.65',
    symbol: 'SPOT',
  },
] as const;

const CASH_PANEL: PortfolioCashPanel = {
  actionLabel: 'Add Cash',
  balanceLabel: 'Current Balance',
  balanceValue: '$5,750,20',
  periodLabel: 'Month',
  title: 'Add Cash',
};

function fetchMetricCards(): Promise<readonly PortfolioMetricCard[]> {
  return Promise.resolve(METRIC_CARDS);
}

function fetchTickerPanel(): Promise<{
  tickerEditorLabel: string;
  tickerPanelTitle: string;
  tickers: readonly PortfolioTicker[];
}> {
  return Promise.resolve({
    tickerEditorLabel: TICKER_EDITOR_LABEL,
    tickerPanelTitle: TICKER_PANEL_TITLE,
    tickers: TICKERS,
  });
}

function fetchCashPanel(): Promise<PortfolioCashPanel> {
  return Promise.resolve(CASH_PANEL);
}

export async function loadPortfolioScreenData(): Promise<PortfolioScreenData> {
  const [shell, holdingsSections, metricCards, tickerPanel, cashPanel, actionsRail, summaryPanel] =
    await Promise.all([
      loadAtlasShell('/'),
      loadHoldingsSections(),
      fetchMetricCards(),
      fetchTickerPanel(),
      fetchCashPanel(),
      loadActionsRail(),
      loadSummaryPanel(),
    ]);

  return {
    ...actionsRail,
    ...shell,
    ...summaryPanel,
    ...tickerPanel,
    cashPanel,
    holdingsSections,
    metricCards,
  };
}
