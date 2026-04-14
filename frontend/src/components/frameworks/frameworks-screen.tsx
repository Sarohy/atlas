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
  if (card.options !== undefined && card.selectedValue !== undefined) {
    return (
      <article className={cn('atlas-frameworks-overview-card', `is-${card.tone}`)}>
        <label className="atlas-frameworks-overview-label" htmlFor="framework-initial-catalyst-select">
          {card.label}
        </label>
        <select
          className={cn('atlas-frameworks-overview-value', 'atlas-frameworks-overview-select', `is-${card.tone}`)}
          data-testid="framework-initial-catalyst-select"
          defaultValue={card.selectedValue}
          id="framework-initial-catalyst-select"
        >
          {card.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        {card.detail ? <p className="atlas-frameworks-overview-detail">{card.detail}</p> : null}
      </article>
    );
  }

  return (
    <article className={cn('atlas-frameworks-overview-card', `is-${card.tone}`)}>
      <p className="atlas-frameworks-overview-label">{card.label}</p>
      <p className={cn('atlas-frameworks-overview-value', `is-${card.tone}`)}>{card.value}</p>
      <p className="atlas-frameworks-overview-detail">{card.detail}</p>
    </article>
  );
}
