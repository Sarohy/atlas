import { LogoutButton } from '@/components/auth/logout-button';
import { cn } from '@/lib/utils';
import type {
  PortfolioHoldingSection,
  PortfolioNavItem,
  PortfolioScreenData,
  PortfolioSummaryRow,
} from '@/types/portfolio';

export function AtlasHeader({ appTitle }: { appTitle: string }) {
  return (
    <header className="atlas-portfolio-topbar">
      <div className="atlas-portfolio-wordmark">{appTitle}</div>
      <LogoutButton />
    </header>
  );
}

export function AtlasNavigation({ labels }: { labels: readonly PortfolioNavItem[] }) {
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

export function AtlasHoldingsRail({ sections }: { sections: readonly PortfolioHoldingSection[] }) {
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

export function AtlasActionsRail({
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
