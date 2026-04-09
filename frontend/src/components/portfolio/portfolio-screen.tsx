import { LiveCashPanel, LiveMetricsGrid } from '@/components/atlas/atlas-chrome';
import { PortfolioTickersPanel } from './portfolio-tickers-panel';

export function PortfolioScreen() {
  return (
    <main className="atlas-portfolio-main" data-testid="atlas-portfolio-page">
      <LiveMetricsGrid />
      <div className="atlas-portfolio-main-grid">
        <PortfolioTickersPanel />
        <LiveCashPanel />
      </div>
    </main>
  );
}
