'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import {
  AtlasActionsRail,
  AtlasHeader,
  AtlasHoldingsRail,
  AtlasNavigation,
} from '@/components/atlas/atlas-chrome';
import { WatchlistTable } from './watchlist-table';
import type { WatchlistScreenData } from '@/lib/api/watchlist-shell';

// Module-level singleton — safe because this is client-only ('use client').
const queryClient = new QueryClient();

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

export function WatchlistScreen({ data }: { data: WatchlistScreenData }) {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="atlas-portfolio-shell" data-testid="atlas-watchlist-page">
        <AtlasHeader appTitle={data.appTitle} />
        <AtlasNavigation labels={data.navItems} />
        <div className="atlas-portfolio-layout">
          <AtlasHoldingsRail />
          <WatchlistContent />
          <AtlasActionsRail actions={data.actions} title={data.actionsTitle} />
        </div>
      </div>
    </QueryClientProvider>
  );
}

// Re-export screen data type so the page import is clean.
export type { WatchlistScreenData };
