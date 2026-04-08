import { loadAtlasShell, loadActionsRail, loadSummaryPanel } from './atlas-shell';
import type { PortfolioScreenData } from '@/types/portfolio';

export type ClustersScreenData = Pick<
  PortfolioScreenData,
  | 'appTitle'
  | 'logoutLabel'
  | 'navItems'
  | 'actions'
  | 'actionsTitle'
  | 'summaryRows'
  | 'summaryTitle'
>;

export async function loadClustersScreenData(): Promise<ClustersScreenData> {
  const [shell, actionsRail, summaryPanel] = await Promise.all([
    loadAtlasShell('/clusters'),
    loadActionsRail(),
    loadSummaryPanel(),
  ]);
  return { ...shell, ...actionsRail, ...summaryPanel };
}
