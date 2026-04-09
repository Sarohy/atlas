'use client';

import { WatchlistTable } from './watchlist-table';

// ─── Content ──────────────────────────────────────────────────────────────────

function WatchlistContent() {
  return (
    <div className="atlas-portfolio-main" style={{ padding: '20px 24px' }}>
      {/* Page heading */}
      <div className="mb-5">
        <h1
          className="font-mono font-bold text-base tracking-widest uppercase"
          style={{ color: '#e8edf5' }}
        >
          Watchlist
        </h1>
        <p className="mt-0.5 text-xs" style={{ color: '#4a5568' }}>
          Monitor tickers without a position — price, day change, and 1-year beta vs SPY.
        </p>
      </div>

      <WatchlistTable />
    </div>
  );
}

// ─── Screen ───────────────────────────────────────────────────────────────────

export function WatchlistScreen() {
  return <WatchlistContent />;
}
