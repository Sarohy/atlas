import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, afterEach } from 'vitest';

import { AddPositionDialog } from '@/components/portfolio/add-position-dialog';
import type { TickerResponse } from '@/lib/schemas/ticker';

vi.mock('@/lib/api/tickers', () => ({
  fetchTickers: vi.fn().mockResolvedValue([]),
  createTicker: vi.fn().mockResolvedValue({
    id: 2,
    ticker: 'NVDA',
    company_name: 'NVIDIA Corporation',
    shares: 25,
    created_at: '2026-04-07T00:00:00Z',
    updated_at: '2026-04-07T00:00:00Z',
  }),
  updateTicker: vi.fn().mockResolvedValue({
    id: 1,
    ticker: 'AAPL',
    company_name: 'Apple Inc.',
    shares: 200,
    created_at: '2026-04-07T00:00:00Z',
    updated_at: '2026-04-07T00:00:00Z',
  }),
  deleteTicker: vi.fn().mockResolvedValue(undefined),
  searchTickers: vi
    .fn()
    .mockResolvedValue([
      { ticker: 'NVDA', name: 'NVIDIA Corporation', market: 'stocks', type: 'CS' },
    ]),
}));

afterEach(() => vi.clearAllMocks());

const EDIT_TARGET: TickerResponse = {
  id: 1,
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  shares: 100,
  created_at: '2026-04-07T00:00:00Z',
  updated_at: '2026-04-07T00:00:00Z',
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('AddPositionDialog — edit mode', () => {
  it('renders the edit heading with the ticker name', () => {
    render(<AddPositionDialog open={true} onClose={vi.fn()} editTarget={EDIT_TARGET} />, {
      wrapper,
    });
    expect(screen.getByText('Edit AAPL')).toBeInTheDocument();
  });

  it('pre-fills shares from the edit target', () => {
    render(<AddPositionDialog open={true} onClose={vi.fn()} editTarget={EDIT_TARGET} />, {
      wrapper,
    });
    const input = screen.getByPlaceholderText('0.0000');
    expect((input as HTMLInputElement).value).toBe('100');
  });

  it('calls onClose when ✕ button is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<AddPositionDialog open={true} onClose={onClose} editTarget={EDIT_TARGET} />, {
      wrapper,
    });
    await user.click(screen.getByRole('button', { name: '✕' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('submits updated shares and calls onClose', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<AddPositionDialog open={true} onClose={onClose} editTarget={EDIT_TARGET} />, {
      wrapper,
    });
    const sharesInput = screen.getByPlaceholderText('0.0000');
    await user.clear(sharesInput);
    await user.type(sharesInput, '200');
    await user.click(screen.getByRole('button', { name: 'Update Shares' }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});

describe('AddPositionDialog — create mode', () => {
  it('renders the "Add Position" heading', () => {
    render(<AddPositionDialog open={true} onClose={vi.fn()} editTarget={null} />, { wrapper });
    expect(screen.getByText('Add Position')).toBeInTheDocument();
  });

  it('shows ticker search field in create mode', () => {
    render(<AddPositionDialog open={true} onClose={vi.fn()} editTarget={null} />, { wrapper });
    expect(screen.getByPlaceholderText('Search ticker or company…')).toBeInTheDocument();
  });

  it('does not render when open=false', () => {
    render(<AddPositionDialog open={false} onClose={vi.fn()} editTarget={null} />, { wrapper });
    expect(screen.queryByText('Add Position')).not.toBeInTheDocument();
  });

  it('shows shares input after selecting a ticker', async () => {
    const user = userEvent.setup();
    render(<AddPositionDialog open={true} onClose={vi.fn()} editTarget={null} />, { wrapper });
    await user.type(screen.getByPlaceholderText('Search ticker or company…'), 'nvda');
    await waitFor(() => screen.getByText('NVIDIA Corporation'));
    await user.click(screen.getByText('NVIDIA Corporation'));
    expect(screen.getByPlaceholderText('0.0000')).toBeInTheDocument();
  });

  it('can clear the selected ticker to search again', async () => {
    const user = userEvent.setup();
    render(<AddPositionDialog open={true} onClose={vi.fn()} editTarget={null} />, { wrapper });
    await user.type(screen.getByPlaceholderText('Search ticker or company…'), 'nvda');
    await waitFor(() => screen.getByText('NVIDIA Corporation'));
    await user.click(screen.getByText('NVIDIA Corporation'));
    // Two ✕ buttons now exist: dialog close + ticker clear — click the smaller one (ticker clear)
    const clearButtons = screen.getAllByRole('button', { name: '✕' });
    const tickerClearButton = clearButtons.find((btn) => btn.classList.contains('text-xs'));
    expect(tickerClearButton).toBeDefined();
    await user.click(tickerClearButton as HTMLElement);
    // Search input should be back
    expect(screen.getByPlaceholderText('Search ticker or company…')).toBeInTheDocument();
  });
});
