'use client';

import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { PortfolioTable } from '@/components/portfolio/portfolio-table';
import { AddPositionDialog } from '@/components/portfolio/add-position-dialog';

/** Singleton QueryClient for this page. */
const queryClient = new QueryClient();

export default function PortfolioPage() {
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <QueryClientProvider client={queryClient}>
      <main className="min-h-screen bg-[#0a0e1a] px-6 py-8">
        {/* Page header */}
        <div className="mb-8 flex items-end justify-between">
          <div>
            <h1 className="font-mono font-bold text-2xl tracking-widest text-[#e8edf5] uppercase">
              Portfolio
            </h1>
            <p className="mt-1 text-sm text-[#8a95a8]">
              Manage your holdings — shares are updated post-close only.
            </p>
          </div>
          <button
            onClick={() => setDialogOpen(true)}
            className="px-4 py-2 bg-[#4a90d9] hover:bg-[#3a7bc8] text-[#0a0e1a] font-mono font-bold text-sm rounded transition-colors"
          >
            + Add Position
          </button>
        </div>

        {/* Positions table */}
        <PortfolioTable />

        {/* Add dialog */}
        <AddPositionDialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          editTarget={null}
        />
      </main>
    </QueryClientProvider>
  );
}
