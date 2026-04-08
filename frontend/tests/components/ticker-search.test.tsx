import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { TickerSearch } from '@/components/portfolio/ticker-search';
import { server } from '../mocks/server';

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('TickerSearch', () => {
  it('renders a search input', () => {
    render(<TickerSearch onSelect={vi.fn()} />, { wrapper });
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('shows ticker results after typing', async () => {
    const user = userEvent.setup();
    render(<TickerSearch onSelect={vi.fn()} />, { wrapper });
    const input = screen.getByRole('textbox');
    await user.type(input, 'apple');
    await waitFor(() => expect(screen.getByText('Apple Inc.')).toBeInTheDocument());
  });

  it('calls onSelect when a result is clicked', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<TickerSearch onSelect={onSelect} />, { wrapper });
    await user.type(screen.getByRole('textbox'), 'apple');
    await waitFor(() => screen.getByText('Apple Inc.'));
    await user.click(screen.getByText('Apple Inc.'));
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ ticker: 'AAPL', name: 'Apple Inc.' }),
    );
  });

  it('shows "No results" when the API returns an empty list', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/tickers/search', () => HttpResponse.json([])),
    );
    const user = userEvent.setup();
    render(<TickerSearch onSelect={vi.fn()} />, { wrapper });
    await user.type(screen.getByRole('textbox'), 'zzz');
    await waitFor(() => expect(screen.getByText(/No results for/i)).toBeInTheDocument());
  });
});
