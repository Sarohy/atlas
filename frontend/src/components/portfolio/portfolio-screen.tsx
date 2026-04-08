import {
  AtlasActionsRail,
  AtlasHeader,
  AtlasHoldingsRail,
  AtlasNavigation,
  LiveCashPanel,
  LiveMetricsGrid,
} from '@/components/atlas/atlas-chrome';
import type { PortfolioScreenData } from '@/types/portfolio';
import { PortfolioTickersPanel } from './portfolio-tickers-panel';

type PortfolioScreenProps = {
  data: PortfolioScreenData;
};

export function PortfolioScreen({ data }: PortfolioScreenProps) {
  return (
    <div className="atlas-portfolio-shell" data-testid="atlas-portfolio-page">
      <AtlasHeader appTitle={data.appTitle} />
      <AtlasNavigation labels={data.navItems} />
      <div className="atlas-portfolio-layout">
        <AtlasHoldingsRail />
        <main className="atlas-portfolio-main">
          <LiveMetricsGrid />
          <div className="atlas-portfolio-main-grid">
            <PortfolioTickersPanel />
            <LiveCashPanel />
          </div>
        </main>
        <AtlasActionsRail actions={data.actions} title={data.actionsTitle} />
      </div>
    </div>
  );
}
