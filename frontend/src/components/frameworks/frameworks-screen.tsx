import { cn } from '@/lib/utils';
import type { FrameworkOverviewCard, FrameworksScreenData } from '@/types/frameworks';
import { FrameworksPanelsSection } from './frameworks-panels-section';

type FrameworksScreenProps = {
  data: FrameworksScreenData;
};

export function FrameworksScreen({ data }: FrameworksScreenProps) {
  return (
    <main
      className="atlas-portfolio-main atlas-frameworks-main"
      data-testid="atlas-frameworks-page"
    >
      <section className="atlas-frameworks-overview">
        {data.overviewCards.map((card) => (
          <OverviewCard card={card} key={card.label} />
        ))}
      </section>

      <FrameworksPanelsSection />
    </main>
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
