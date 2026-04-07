import {
  AtlasActionsRail,
  AtlasHeader,
  AtlasHoldingsRail,
  AtlasNavigation,
} from '@/components/atlas/atlas-chrome';
import { cn } from '@/lib/utils';
import type {
  BriefingDeployPlanRow,
  BriefingPositionRow,
  BriefingProFormaRow,
  BriefingSummaryStat,
  BriefingTriggerRow,
  DailyBriefingScreenData,
} from '@/types/daily-briefing';

type DailyBriefingScreenProps = {
  data: DailyBriefingScreenData;
};

export function DailyBriefingScreen({ data }: DailyBriefingScreenProps) {
  return (
    <div className="atlas-portfolio-shell" data-testid="atlas-daily-briefing-page">
      <AtlasHeader appTitle={data.appTitle} />
      <AtlasNavigation labels={data.navItems} />
      <div className="atlas-portfolio-layout">
        <AtlasHoldingsRail sections={data.holdingsSections} />
        <main className="atlas-portfolio-main atlas-briefing-main">
          <section className="atlas-briefing-hero">
            <div>
              <h1 className="atlas-briefing-title">{data.briefingDate}</h1>
              <p className="atlas-briefing-subtitle">{data.briefingSubtitle}</p>
            </div>
            <span className={cn('atlas-briefing-badge', `is-${data.badgeTone}`)}>
              {data.badgeLabel}
            </span>
          </section>

          <div className="atlas-briefing-grid">
            <div className="atlas-briefing-column">
              {data.questionSections.map((section) => (
                <section className="atlas-briefing-block" key={section.title}>
                  <h2 className="atlas-briefing-question">{section.title}</h2>
                  <div className="atlas-briefing-list">
                    {section.rows.map((row) => (
                      <BriefingRow key={`${section.title}-${row.symbol}`} row={row} />
                    ))}
                  </div>
                </section>
              ))}

              <section className="atlas-briefing-block">
                <h2 className="atlas-briefing-question">{data.q2Title}</h2>
                <div className="atlas-briefing-callout">{data.q2Callout}</div>
              </section>

              <section className="atlas-briefing-block">
                <h2 className="atlas-briefing-question">Q5 — What changes this today?</h2>
                <div className="atlas-briefing-trigger-list">
                  {data.triggerRows.map((row) => (
                    <TriggerRow key={row.title} row={row} />
                  ))}
                </div>
              </section>
            </div>

            <div className="atlas-briefing-column">
              <section className="atlas-briefing-block">
                <h2 className="atlas-briefing-question">Q4 — Pro forma after all actions</h2>
                <div className="atlas-briefing-proforma">
                  <div className="atlas-briefing-proforma-header">
                    <span>Ticker</span>
                    <span>Value</span>
                    <span>Wt%</span>
                    <span>Cluster</span>
                    <span>Beta</span>
                    <span>Action</span>
                  </div>
                  {data.proFormaRows.map((row) => (
                    <ProFormaRow key={row.symbol} row={row} />
                  ))}
                </div>
                <div className="atlas-briefing-stats">
                  {data.summaryStats.map((stat) => (
                    <SummaryStat key={stat.label} stat={stat} />
                  ))}
                </div>
              </section>

              <section className="atlas-briefing-block">
                <h2 className="atlas-briefing-question">{data.deployPlanTitle}</h2>
                <div className="atlas-briefing-deploy-table">
                  <div className="atlas-briefing-deploy-header">
                    <span>Ticker</span>
                    <span>Entry</span>
                    <span>Size</span>
                    <span>Phase</span>
                  </div>
                  {data.deployPlanRows.map((row) => (
                    <DeployPlanRow key={row.symbol} row={row} />
                  ))}
                </div>
              </section>
            </div>
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

function BriefingRow({ row }: { row: BriefingPositionRow }) {
  return (
    <div className="atlas-briefing-row">
      <span className="atlas-briefing-symbol">{row.symbol}</span>
      <span className="atlas-briefing-body">{row.body}</span>
      <span className={cn('atlas-briefing-status', `is-${row.statusTone}`)}>{row.status}</span>
    </div>
  );
}

function TriggerRow({ row }: { row: BriefingTriggerRow }) {
  return (
    <div className="atlas-briefing-trigger-row">
      <strong>{row.title}</strong> — {row.body}
    </div>
  );
}

function ProFormaRow({ row }: { row: BriefingProFormaRow }) {
  return (
    <div className="atlas-briefing-proforma-row">
      <span className={cn('atlas-briefing-symbol', row.symbol === 'CASH' && 'is-cash')}>
        {row.symbol}
      </span>
      <span>{row.value}</span>
      <span className={cn(row.weightTone ? `is-${row.weightTone}` : undefined)}>{row.weight}</span>
      <span className={cn(row.clusterTone ? `is-${row.clusterTone}` : undefined)}>
        {row.cluster}
      </span>
      <span>{row.beta}</span>
      <span className={cn(row.actionTone ? `is-${row.actionTone}` : undefined)}>{row.action}</span>
    </div>
  );
}

function SummaryStat({ stat }: { stat: BriefingSummaryStat }) {
  return (
    <div className="atlas-briefing-stat-row">
      <span className="atlas-briefing-stat-label">{stat.label}</span>
      <span
        className={cn(
          'atlas-briefing-stat-value',
          stat.tone !== 'default' ? `is-${stat.tone}` : undefined,
        )}
      >
        {stat.value}
      </span>
    </div>
  );
}

function DeployPlanRow({ row }: { row: BriefingDeployPlanRow }) {
  return (
    <div className="atlas-briefing-deploy-row">
      <span className="atlas-briefing-symbol">{row.symbol}</span>
      <span className="is-cyan">{row.entry}</span>
      <span>{row.size}</span>
      <span className="atlas-briefing-phase">{row.phase}</span>
    </div>
  );
}
