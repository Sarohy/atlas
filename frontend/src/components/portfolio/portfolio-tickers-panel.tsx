'use client';

import { useState } from 'react';

import { useTickers } from '@/lib/hooks/use-tickers';
import { EditTickersDialog } from './edit-tickers-dialog';
import type { TickerResponse } from '@/lib/schemas/ticker';

/** Format a position value compactly: $X.XXM, $XXXK, or — if null. */
function fmtPositionValue(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${Math.round(value)}`;
}

/** Format a nullable percentage value and return value + tone. */
function fmtChange(pct: number | null | undefined): {
  text: string;
  tone: 'green' | 'red' | 'default';
} {
  if (pct == null) return { text: '—', tone: 'default' };
  const sign = pct >= 0 ? '+' : '';
  return {
    text: `${sign}${pct.toFixed(2)}%`,
    tone: pct > 0 ? 'green' : pct < 0 ? 'red' : 'default',
  };
}

function TickerRow({ position }: { position: TickerResponse }) {
  const change = fmtChange(position.day_change_pct);
  return (
    <article className="atlas-portfolio-ticker">
      <div className="atlas-portfolio-ticker-badge">{position.ticker.slice(0, 1)}</div>
      <div className="atlas-portfolio-ticker-copy">
        <p className="atlas-portfolio-ticker-symbol">{position.ticker}</p>
        <p className="atlas-portfolio-ticker-label">{position.company_name ?? position.ticker}</p>
      </div>
      <div className="atlas-portfolio-ticker-metrics">
        <p className="atlas-portfolio-ticker-price">{fmtPositionValue(position.position_value)}</p>
        <p className={`atlas-portfolio-ticker-change is-${change.tone}`}>{change.text}</p>
      </div>
    </article>
  );
}

export function PortfolioTickersPanel() {
  const [editOpen, setEditOpen] = useState(false);
  const { data: positions, isLoading } = useTickers();

  return (
    <>
      <section className="atlas-portfolio-panel">
        <div className="atlas-portfolio-panel-header">
          <h2 className="atlas-portfolio-panel-title">All Tickers</h2>
          <button className="atlas-portfolio-link" type="button" onClick={() => setEditOpen(true)}>
            Edit Tickers
          </button>
        </div>

        <div className="atlas-portfolio-ticker-list">
          {isLoading && (
            <p className="atlas-portfolio-ticker-label" style={{ paddingTop: '1rem' }}>
              Loading…
            </p>
          )}

          {!isLoading && (!positions || positions.length === 0) && (
            <p className="atlas-portfolio-ticker-label" style={{ paddingTop: '1rem' }}>
              No positions yet — click Edit Tickers to add one.
            </p>
          )}

          {positions?.map((pos) => (
            <TickerRow key={pos.id} position={pos} />
          ))}
        </div>
      </section>

      <EditTickersDialog open={editOpen} onClose={() => setEditOpen(false)} />
    </>
  );
}
