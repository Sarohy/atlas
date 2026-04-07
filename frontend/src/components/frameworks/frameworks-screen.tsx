import {
  AtlasActionsRail,
  AtlasHeader,
  AtlasHoldingsRail,
  AtlasNavigation,
} from '@/components/atlas/atlas-chrome';
import { cn } from '@/lib/utils';
import type {
  FrameworkCard,
  FrameworkOverviewCard,
  FrameworksScreenData,
} from '@/types/frameworks';

type FrameworksScreenProps = {
  data: FrameworksScreenData;
};

export function FrameworksScreen({ data }: FrameworksScreenProps) {
  return (
    <div className="atlas-portfolio-shell" data-testid="atlas-frameworks-page">
      <AtlasHeader appTitle={data.appTitle} />
      <AtlasNavigation labels={data.navItems} />
      <div className="atlas-portfolio-layout">
        <AtlasHoldingsRail />
        <main className="atlas-portfolio-main atlas-frameworks-main">
          <section className="atlas-frameworks-overview">
            {data.overviewCards.map((card) => (
              <OverviewCard card={card} key={card.label} />
            ))}
          </section>

          <section className="atlas-frameworks-cards">
            {data.frameworks.map((framework) => (
              <FrameworkRuleCard framework={framework} key={framework.title} />
            ))}
          </section>
        </main>
        <AtlasActionsRail actions={data.actions} title={data.actionsTitle} />
      </div>
    </div>
  );
}

function OverviewCard({ card }: { card: FrameworkOverviewCard }) {
  return (
    <article className={cn('atlas-frameworks-overview-card', `is-${card.tone}`)}>
      <p className="atlas-frameworks-overview-label">{card.label}</p>
      <p className={cn('atlas-frameworks-overview-value', `is-${card.tone}`)}>{card.value}</p>
      <p className="atlas-frameworks-overview-detail">{card.detail}</p>
    </article>
  );
}

function FrameworkRuleCard({ framework }: { framework: FrameworkCard }) {
  return (
    <article className="atlas-frameworks-panel atlas-frameworks-rule-card">
      <header className="atlas-frameworks-panel-header">
        <h2 className="atlas-frameworks-panel-title">{framework.title}</h2>
        <span className={cn('atlas-frameworks-pill', `is-${framework.statusTone}`)}>
          {framework.status}
        </span>
      </header>
      <p className="atlas-frameworks-summary">{framework.summary}</p>
      <p className="atlas-frameworks-rule">{framework.rule}</p>
    </article>
  );
}
