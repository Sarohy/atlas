import { LogoutButton } from '@/components/auth/logout-button';
import { cn } from '@/lib/utils';
import type {
  PortfolioMetricCard,
  PortfolioScreenData,
  PortfolioSummaryRow,
  PortfolioTicker,
} from '@/types/portfolio';

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
            <TickerPanel
              editorLabel={data.tickerEditorLabel}
              tickers={data.tickers}
              title={data.tickerPanelTitle}
            />
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

function AtlasHeader({ appTitle }: Pick<PortfolioScreenData, 'appTitle'>) {
  return (
    <header className="atlas-portfolio-topbar">
      <div className="atlas-portfolio-wordmark">{appTitle}</div>
      <LogoutButton />
    </header>
  );
}

function AtlasNavigation({
  labels,
}: {
  labels: readonly PortfolioScreenData['navItems'][number][];
}) {
  return (
    <nav aria-label="Primary" className="atlas-portfolio-nav">
      {labels.map((item) => (
        <a
          aria-current={item.isActive ? 'page' : undefined}
          className={cn('atlas-portfolio-nav-item', item.isActive && 'is-active')}
          href={item.href}
          key={item.label}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

function AtlasHoldingsRail({ sections }: { sections: PortfolioScreenData['holdingsSections'] }) {
  return (
    <aside className="atlas-portfolio-side atlas-portfolio-side--left">
      {sections.map((section) => (
        <section className="atlas-portfolio-side-section" key={section.title}>
          <h2 className="atlas-portfolio-side-title">{section.title}</h2>
          <div>
            {section.items.map((item) => (
              <article className="atlas-portfolio-holding" key={item.symbol}>
                <div className="atlas-portfolio-holding-row">
                  <span
                    className={cn(
                      'atlas-portfolio-holding-symbol',
                      item.symbol === 'CASH' && 'is-cash',
                    )}
                  >
                    {item.symbol}
                  </span>
                  <span className="atlas-portfolio-holding-value">{item.value}</span>
                </div>
                <div className="atlas-portfolio-progress">
                  <span
                    className={cn('atlas-portfolio-progress-bar', `is-${item.progressTone}`)}
                    style={{ width: `${item.progressValue}%` }}
                  />
                </div>
                <div className="atlas-portfolio-holding-row atlas-portfolio-holding-row--meta">
                  <span className="atlas-portfolio-holding-meta">{item.allocation}</span>
                  <span
                    className={cn('atlas-portfolio-holding-change', `is-${item.dayChangeTone}`)}
                  >
                    {item.dayChange}
                  </span>
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </aside>
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

function TickerPanel({
  editorLabel,
  tickers,
  title,
}: {
  editorLabel: string;
  tickers: readonly PortfolioTicker[];
  title: string;
}) {
  return (
    <section className="atlas-portfolio-panel">
      <div className="atlas-portfolio-panel-header">
        <h2 className="atlas-portfolio-panel-title">{title}</h2>
        <button className="atlas-portfolio-link" type="button">
          {editorLabel}
        </button>
      </div>
      <div className="atlas-portfolio-ticker-list">
        {tickers.map((ticker, index) => (
          <article
            className="atlas-portfolio-ticker"
            key={`${ticker.symbol}-${ticker.label}-${index}`}
          >
            <div className="atlas-portfolio-ticker-badge">{ticker.symbol.slice(0, 1)}</div>
            <div className="atlas-portfolio-ticker-copy">
              <p className="atlas-portfolio-ticker-symbol">{ticker.symbol}</p>
              <p className="atlas-portfolio-ticker-label">{ticker.label}</p>
            </div>
            <div className="atlas-portfolio-ticker-metrics">
              <p className="atlas-portfolio-ticker-price">{ticker.price}</p>
              <p className={cn('atlas-portfolio-ticker-change', `is-${ticker.changeTone}`)}>
                {ticker.change}
              </p>
            </div>
          </article>
        ))}
      </div>
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

function AtlasActionsRail({
  actions,
  summaryRows,
  summaryTitle,
  title,
}: {
  actions: PortfolioScreenData['actions'];
  summaryRows: PortfolioScreenData['summaryRows'];
  summaryTitle: string;
  title: string;
}) {
  return (
    <aside className="atlas-portfolio-side atlas-portfolio-side--right">
      <section className="atlas-portfolio-side-section">
        <h2 className="atlas-portfolio-side-title">{title}</h2>
        <div>
          {actions.map((action) => (
            <article className="atlas-portfolio-action" key={`${action.title}-${action.metadata}`}>
              <span className={cn('atlas-portfolio-action-dot', `is-${action.tone}`)} />
              <div className="atlas-portfolio-action-copy">
                <p className="atlas-portfolio-action-text">
                  <strong>{action.title}</strong> {action.description}
                </p>
                <p className="atlas-portfolio-action-meta">{action.metadata}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="atlas-portfolio-side-section">
        <h2 className="atlas-portfolio-side-title">{summaryTitle}</h2>
        <div>
          {summaryRows.map((row) => (
            <SummaryRow key={row.label} row={row} />
          ))}
        </div>
      </section>
    </aside>
  );
}

function SummaryRow({ row }: { row: PortfolioSummaryRow }) {
  return (
    <div className="atlas-portfolio-summary-row">
      <span className="atlas-portfolio-summary-label">{row.label}</span>
      <span className={cn('atlas-portfolio-summary-value', getSummaryToneClass(row.tone))}>
        {row.value}
      </span>
    </div>
  );
}

function getSummaryToneClass(tone: PortfolioSummaryRow['tone']) {
  return tone === 'default' ? undefined : `is-${tone}`;
}
