import {
  AtlasActionsRail,
  AtlasHeader,
  AtlasHoldingsRail,
  AtlasNavigation,
} from '@/components/atlas/atlas-chrome';
import { cn } from '@/lib/utils';
import type { PortfolioMetricCard, PortfolioScreenData } from '@/types/portfolio';
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
        <AtlasHoldingsRail sections={data.holdingsSections} />
        <main className="atlas-portfolio-main">
          <AtlasMetricsGrid cards={data.metricCards} />
          <div className="atlas-portfolio-main-grid">
            <PortfolioTickersPanel />
            <CashPanel
              actionLabel={data.cashPanel.actionLabel}
              balanceLabel={data.cashPanel.balanceLabel}
              balanceValue={data.cashPanel.balanceValue}
              periodLabel={data.cashPanel.periodLabel}
              title={data.cashPanel.title}
            />
          </div>
        </main>
        <AtlasActionsRail
          actions={data.actions}
          summaryRows={data.summaryRows}
          summaryTitle={data.summaryTitle}
          title={data.actionsTitle}
        />
      </div>
    </div>
  );
}

function AtlasMetricsGrid({ cards }: { cards: readonly PortfolioMetricCard[] }) {
  return (
    <section className="atlas-portfolio-metrics">
      {cards.map((card) => (
        <article className={cn('atlas-portfolio-metric-card', `is-${card.tone}`)} key={card.label}>
          <p className="atlas-portfolio-metric-label">{card.label}</p>
          <p
            className={cn(
              'atlas-portfolio-metric-value',
              card.valueTone ? `is-${card.valueTone}` : undefined,
            )}
          >
            {card.value}
          </p>
          <p className="atlas-portfolio-metric-detail">{card.detail}</p>
        </article>
      ))}
    </section>
  );
}

function CashPanel({
  actionLabel,
  balanceLabel,
  balanceValue,
  periodLabel,
  title,
}: PortfolioScreenData['cashPanel']) {
  return (
    <section className="atlas-portfolio-panel">
      <div className="atlas-portfolio-panel-header atlas-portfolio-panel-header--cash">
        <h2 className="atlas-portfolio-panel-title">{title}</h2>
        <button className="atlas-portfolio-select" type="button">
          <span>{periodLabel}</span>
          <span aria-hidden="true">v</span>
        </button>
      </div>
      <div className="atlas-portfolio-cash-card">
        <div className="atlas-portfolio-cash-icon" aria-hidden="true">
          $
        </div>
        <p className="atlas-portfolio-cash-label">{balanceLabel}</p>
        <p className="atlas-portfolio-cash-value">{balanceValue}</p>
      </div>
      <div className="atlas-portfolio-cash-input-row">
        <div className="atlas-portfolio-cash-input">{actionLabel}</div>
        <button className="atlas-portfolio-cash-submit" type="button">
          {'>'}
        </button>
      </div>
    </section>
  );
}
