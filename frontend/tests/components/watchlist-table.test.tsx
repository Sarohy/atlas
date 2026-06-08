import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WatchlistTable } from '@/components/watchlist/watchlist-table';

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return Wrapper;
}

function watchlistItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    ticker: 'APPB',
    company_name: 'APPLIED BIOSCIENCES CORP',
    current_price: null,
    previous_close: null,
    day_change: null,
    day_change_pct: null,
    beta: null,
    synced_at: null,
    created_at: '2026-06-08T00:00:00Z',
    updated_at: '2026-06-08T00:00:00Z',
    ...overrides,
  };
}

const mocks = vi.hoisted(() => ({
  watchlist: [] as Record<string, unknown>[],
  portfolio: [] as Record<string, unknown>[],
  createMutate: vi.fn(),
  removeMutate: vi.fn(),
}));

vi.mock('@/lib/hooks/use-watchlist', () => ({
  useWatchlist: () => ({ data: mocks.watchlist, isLoading: false }),
  useRemoveFromWatchlist: () => ({ mutate: mocks.removeMutate, isPending: false }),
  useSyncWatchlist: () => ({ mutate: vi.fn(), isPending: false }),
  useAddToWatchlist: () => ({ mutate: vi.fn(), isPending: false, error: null }),
}));

vi.mock('@/lib/hooks/use-tickers', () => ({
  useTickers: () => ({ data: mocks.portfolio }),
  useCreateTicker: () => ({ mutate: mocks.createMutate, isPending: false, error: null }),
}));

describe('WatchlistTable — Add to portfolio', () => {
  beforeEach(() => {
    mocks.watchlist = [watchlistItem()];
    mocks.portfolio = [];
    mocks.createMutate.mockReset();
    mocks.removeMutate.mockReset();
  });

  it('adds a watchlist ticker to the portfolio with the entered shares', async () => {
    const user = userEvent.setup();
    render(<WatchlistTable />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole('button', { name: 'Add to portfolio' }));

    // Dialog opens pre-filled with the ticker.
    expect(screen.getByRole('heading', { name: 'Add to Portfolio' })).toBeInTheDocument();

    await user.type(screen.getByLabelText('Shares'), '10');
    await user.click(screen.getByRole('button', { name: 'Add to Portfolio' }));

    expect(mocks.createMutate).toHaveBeenCalledTimes(1);
    expect(mocks.createMutate).toHaveBeenCalledWith(
      {
        ticker: 'APPB',
        company_name: 'APPLIED BIOSCIENCES CORP',
        shares: 10,
        cluster_id: null,
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it('does not submit when shares is empty or non-positive', async () => {
    const user = userEvent.setup();
    render(<WatchlistTable />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole('button', { name: 'Add to portfolio' }));

    // Submit disabled with no shares entered.
    const submit = screen.getByRole('button', { name: 'Add to Portfolio' });
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText('Shares'), '0');
    expect(submit).toBeDisabled();
    expect(mocks.createMutate).not.toHaveBeenCalled();
  });

  it('disables the add action for tickers already in the portfolio', async () => {
    mocks.portfolio = [{ ticker: 'APPB' }];
    render(<WatchlistTable />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'In portfolio' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'In portfolio' })).toBeDisabled();
  });
});
