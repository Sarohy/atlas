import { loadAtlasShell, loadActionsRail, loadSummaryPanel } from './atlas-shell';
import type { PortfolioScreenData } from '@/types/portfolio';

export type WatchlistScreenData = Pick<
  PortfolioScreenData,
  | 'appTitle'
  | 'logoutLabel'
  | 'navItems'
  | 'actions'
  | 'actionsTitle'
  | 'summaryRows'
  | 'summaryTitle'
>;

export async function loadWatchlistScreenData(): Promise<WatchlistScreenData> {
  const [shell, actionsRail, summaryPanel] = await Promise.all([
    loadAtlasShell('/watchlist'),
    loadActionsRail(),
    loadSummaryPanel(),
  ]);
  return { ...shell, ...actionsRail, ...summaryPanel };
}
